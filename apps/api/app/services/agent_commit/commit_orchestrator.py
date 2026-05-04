"""Orchestrate agent → studio commit: idempotency + lean-payload enrichment + asset sync + chapter/panel."""
from __future__ import annotations

import logging
import uuid
from typing import Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.chapter import Chapter
from app.models.panel import Panel
from app.schemas.agent_commit import CommitToStudioRequest
from app.core.storage import storage_client
from app.services.agent_commit.asset_sync import sync_character, sync_scene
from app.services.agent_commit.conversation_reader import enrich_request_from_conversation
from app.services.agent_commit.idempotency import find_existing_chapter
from app.services.agent_commit.image_fetcher import fetch_and_persist, ImageFetchError
from app.services.agent_commit.spec_builder import build_chapter_source, build_panel_spec
from app.services.binding import refresh_chapter_bindings

logger = logging.getLogger(__name__)


class CommitResult:
    def __init__(self, chapter, status, character_count, scene_count, panel_count, warnings, payload_source):
        self.chapter = chapter
        self.status = status
        self.character_count = character_count
        self.scene_count = scene_count
        self.panel_count = panel_count
        self.warnings = warnings
        self.payload_source = payload_source  # "request" | "conversation"


async def commit_agent_to_studio(
    db: Session,
    project_id: str,
    req: CommitToStudioRequest,
) -> CommitResult:
    """Idempotent commit. Caller owns the DB session + outer transaction."""
    warnings: List[str] = []

    # Lean-payload fallback: if any top-level field is empty, enrich from conversation messages.
    enriched, enrich_warnings = enrich_request_from_conversation(db, req)
    warnings.extend(enrich_warnings)
    payload_source = "conversation" if (
        (len(req.panels) == 0 and len(enriched.panels) > 0)
        or (len(req.characters) == 0 and len(enriched.characters) > 0)
        or (len(req.scenes) == 0 and len(enriched.scenes) > 0)
    ) else "request"
    req = enriched

    existing = find_existing_chapter(
        db, project_id=project_id,
        conversation_id=req.conversation_id, episode_number=req.episode_number,
    )
    if existing is not None:
        return CommitResult(existing, "already_exists", 0, 0, 0, [], payload_source)

    max_order = db.query(func.max(Chapter.order_index)).filter(
        Chapter.project_id == project_id).scalar()
    next_order = (max_order or -1) + 1

    chapter = Chapter(
        id=str(uuid.uuid4()),
        project_id=project_id,
        title=f"第{req.episode_number}集 {req.episode_title}".strip(),
        description=req.outline_summary,
        order_index=next_order,
        script_raw=req.outline_summary,
        layout_json={"source": build_chapter_source(
            conversation_id=req.conversation_id,
            episode_number=req.episode_number,
            art_style=req.art_style,
        )},
        status="draft",
    )
    db.add(chapter); db.flush()

    character_name_to_id: Dict[str, str] = {}
    scene_name_to_id: Dict[str, str] = {}

    for ch_char in req.characters:
        aid, w = await sync_character(db, project_id, ch_char,
                                      source_conversation_id=req.conversation_id)
        character_name_to_id[ch_char.name] = aid
        warnings.extend(w)

    for sc in req.scenes:
        sid, w = await sync_scene(db, project_id, sc,
                                  source_conversation_id=req.conversation_id)
        scene_name_to_id[sc.name] = sid
        warnings.extend(w)

    for idx, agent_panel in enumerate(req.panels):
        panel_id = str(uuid.uuid4())
        spec = build_panel_spec(
            agent_panel, panel_id=panel_id,
            character_name_to_id=character_name_to_id,
            scene_name_to_id=scene_name_to_id,
            art_style=req.art_style,
        )

        preview_key = None
        if agent_panel.temp_image_url:
            try:
                preview_key = await fetch_and_persist(
                    agent_panel.temp_image_url,
                    project_id=project_id, asset_type="panel",
                    name_hint=f"ep{req.episode_number}-p{agent_panel.order}",
                )
            except ImageFetchError as e:
                warnings.append(f"panel #{agent_panel.order} preview failed: {e}")

        # ``fetch_and_persist`` returns a raw MinIO storage key. The Panel
        # model only has ``preview_url`` (no separate key column), and the
        # frontend renders this directly as ``<img src>`` — so we must
        # convert the key into a presigned URL before persisting. ``get_url``
        # returns "" when the storage backend is unavailable; coerce that to
        # ``None`` so the column stays NULL rather than an empty-string URL.
        # TODO: a separate ``preview_key`` column on Panel would let us
        # re-sign URLs cheaply when they expire instead of having to
        # regenerate from the original source.
        preview_url = None
        if preview_key:
            signed = storage_client.get_url(preview_key, expires=3600)
            preview_url = signed or None

        panel = Panel(
            id=panel_id, chapter_id=chapter.id,
            order_index=agent_panel.order if agent_panel.order is not None else idx,
            title=f"Panel {idx + 1}",
            summary=agent_panel.scene_description[:255] if agent_panel.scene_description else None,
            spec_json=spec, render_status="draft", preview_url=preview_url,
        )
        db.add(panel)

    db.flush()
    refresh_chapter_bindings(db, chapter.id)

    return CommitResult(
        chapter, "created",
        len(req.characters), len(req.scenes), len(req.panels),
        warnings, payload_source,
    )
