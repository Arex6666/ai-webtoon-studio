"""Panel image generation orchestration — shared by the
``/agent/episode/{N}/generate-panels`` HTTP endpoint and the
``generate_panels`` agent tool.

Extracted from the route handler in B-1 Phase C so both flows go through
one code path. Two entrypoints:

  * ``generate_panel_images_for_payload`` — the *full-payload* variant the
    HTTP route uses. Caller passes already-resolved
    ``art_style`` / ``characters`` / ``scenes`` / ``panels`` lists. Returns
    a list of ``PanelGenResult`` objects.
  * ``generate_panels_for_episode`` — the *lean* variant the agent tool
    uses. Pulls ``art_style`` / ``characters`` / ``scenes`` / ``panels``
    cards out of the conversation, then delegates to the full-payload
    function. Returns ``{"panels": [...], "warnings": [...]}``.

Both paths persist generated images to MinIO via
``image_fetcher.fetch_and_persist`` and write a ``panels`` card back into
the conversation so a later ``commit_to_studio`` call has the data it
needs.

Note on durations: the loop runs Doubao image generation behind an
``asyncio.Semaphore(5)``; for ~6–10 panels typical wall time is 30–90
seconds. The agent runner exposes the tool with
``expected_duration="slow"`` because of this.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.layer_factory.doubao_image_provider import (
    DoubaoImageRequest,
    get_doubao_image_provider,
)

logger = logging.getLogger(__name__)


@dataclass
class PanelGenResult:
    """Result for a single panel — mirrors PanelResult in the HTTP route.

    Used as the canonical interchange type so callers needn't depend on
    the route's pydantic model.
    """
    id: str
    image_url: Optional[str] = None
    status: str = "failed"  # "success" | "failed"
    error: Optional[str] = None


def _build_prompt(
    *,
    art_style_hint: str,
    scene_part: str,
    char_part: str,
    scene_description: str,
    composition: str,
) -> str:
    parts = [
        art_style_hint,
        scene_part,
        char_part,
        scene_description,
        composition,
        "high quality, detailed, anime illustration",
    ]
    return ", ".join(p for p in parts if p)


async def generate_panel_images_for_payload(
    *,
    episode_number: int,
    project_id: Optional[str],
    art_style: Dict[str, str],
    characters: List[Dict[str, Any]],
    scenes: List[Dict[str, Any]],
    panels: List[Dict[str, Any]],
    concurrency: int = 5,
) -> List[PanelGenResult]:
    """Generate Doubao images for each panel and persist to MinIO.

    Pure-payload variant — does NOT touch the DB. Caller is responsible
    for any persistence beyond the per-image MinIO upload (which the
    fetch_and_persist helper handles itself).

    The dict-shaped arguments mirror the conversation card payloads
    (lower-case key names) AND the HTTP route's pydantic shapes — both
    have the same field names so a model_dump() works as input.
    """
    provider = get_doubao_image_provider()
    if not provider:
        # Replicate route behaviour: return all-failed results so callers
        # can surface a coherent error per panel.
        return [
            PanelGenResult(
                id=str(p.get("id") or f"panel-{i}"),
                status="failed",
                error="Image provider not available (no API key configured)",
            )
            for i, p in enumerate(panels)
        ]

    char_prompt_map = {
        c.get("name"): c.get("visual_prompt")
        for c in characters
        if c.get("name") and c.get("visual_prompt")
    }
    scene_prompt_map = {
        s.get("name"): s.get("visual_prompt")
        for s in scenes
        if s.get("name") and s.get("visual_prompt")
    }
    art_style_hint = (
        f"{art_style.get('base_style', '')}, "
        f"{art_style.get('color_tone', '')}, "
        f"{art_style.get('atmosphere', '')}"
    )

    semaphore = asyncio.Semaphore(concurrency)
    project_id_for_path = project_id or "unknown"

    async def generate_one(panel: Dict[str, Any], idx: int) -> PanelGenResult:
        panel_id = str(panel.get("id") or f"panel-{idx}")
        async with semaphore:
            try:
                scene_name = panel.get("scene_name") or ""
                scene_part = scene_prompt_map.get(scene_name, scene_name)
                panel_chars = panel.get("characters") or []
                char_parts = [char_prompt_map.get(cn, cn) for cn in panel_chars]
                char_part = ", ".join(p for p in char_parts if p)

                prompt = _build_prompt(
                    art_style_hint=art_style_hint,
                    scene_part=scene_part,
                    char_part=char_part,
                    scene_description=panel.get("scene_description") or "",
                    composition=panel.get("composition") or "",
                )

                request = DoubaoImageRequest(
                    prompt=prompt,
                    negative_prompt=(
                        "low quality, blurry, distorted, deformed, ugly, "
                        "text, watermark"
                    ),
                    width=1280,
                    height=720,
                )
                result = await provider.generate(request)
                if not (result.success and result.image_url):
                    return PanelGenResult(
                        id=panel_id,
                        status="failed",
                        error=result.error or "Generation returned no image",
                    )

                # Persist Doubao temp URL → MinIO so commit_to_studio /
                # asset hub can rely on a stable key.
                try:
                    from app.services.agent_commit.image_fetcher import (
                        ImageFetchError,
                        fetch_and_persist,
                    )
                    minio_key = await fetch_and_persist(
                        result.image_url,
                        project_id=project_id_for_path,
                        asset_type="panel",
                        name_hint=f"ep{episode_number}-p{panel_id}",
                    )
                    return PanelGenResult(
                        id=panel_id, image_url=minio_key, status="success",
                    )
                except ImageFetchError as persist_err:
                    logger.warning(
                        "[Episode %s] Panel '%s' MinIO persist failed; "
                        "returning temp URL: %s",
                        episode_number, panel_id, persist_err,
                    )
                    return PanelGenResult(
                        id=panel_id,
                        image_url=result.image_url,
                        status="success",
                        error=f"minio persist failed: {persist_err}",
                    )
            except Exception as e:  # noqa: BLE001 — per-panel isolation
                logger.warning(
                    "[Episode %s] Panel '%s' image failed: %s",
                    episode_number, panel_id, e,
                )
                return PanelGenResult(
                    id=panel_id, status="failed", error=str(e),
                )

    raw = await asyncio.gather(
        *[generate_one(p, i) for i, p in enumerate(panels)],
        return_exceptions=True,
    )
    out: List[PanelGenResult] = []
    for i, r in enumerate(raw):
        if isinstance(r, PanelGenResult):
            out.append(r)
        else:
            panel_id = str(panels[i].get("id") or f"panel-{i}")
            out.append(PanelGenResult(
                id=panel_id, status="failed", error=str(r),
            ))
    return out


def write_panels_card(
    db: Session,
    *,
    conversation_id: str,
    episode_number: int,
    panel_inputs: List[Dict[str, Any]],
    results: List[PanelGenResult],
) -> None:
    """Upsert a `panels` card so a later commit_to_studio can read it.

    Best-effort: failures are logged + swallowed (matches the route's
    behaviour). Caller owns the DB session; we only flush.
    """
    try:
        from app.services.agent_commit.card_writer import (
            build_panels_card,
            upsert_card,
        )

        result_by_id = {r.id: r for r in results}
        merged_panels: List[Dict[str, Any]] = []
        for p in panel_inputs:
            pid = str(p.get("id"))
            r = result_by_id.get(pid)
            merged_panels.append({
                "id": pid,
                "order": p.get("order"),
                "scene_name": p.get("scene_name"),
                "characters": p.get("characters") or [],
                "scene_description": p.get("scene_description") or "",
                "dialogue": p.get("dialogue"),
                "shot_type": p.get("shot_type") or "MS",
                "camera_angle": p.get("camera_angle") or "eye-level",
                "emotion": p.get("emotion"),
                "composition": p.get("composition"),
                "image_url": (
                    r.image_url if r and r.status == "success" else None
                ),
            })

        success_count = sum(1 for r in results if r.status == "success")
        upsert_card(
            db, conversation_id, "panels",
            build_panels_card(merged_panels),
            episode_number=episode_number,
            content_text=(
                f"[panels card · ep{episode_number} · "
                f"{success_count}/{len(results)} ready]"
            ),
        )
    except Exception as e:  # noqa: BLE001 — best-effort
        logger.warning("Failed to write panels card: %s", e)


async def generate_panels_for_episode(
    *,
    db: Session,
    project_id: str,
    episode_number: int,
    conversation_id: Optional[str] = None,
    force_regenerate: bool = False,  # noqa: ARG001 — reserved for future
) -> Dict[str, Any]:
    """Lean entrypoint: read art_style / characters / scenes / panels cards
    out of the conversation and run the generation pipeline.

    Returns a dict
        {
          "panels": [PanelGenResult-dict, ...],
          "warnings": ["..."],
          "panel_count": <int>,
          "success_count": <int>,
        }

    Used by the ``generate_panels`` agent tool. ``conversation_id`` is
    required; the agent runner injects it into the tool context.

    ``force_regenerate`` is accepted for forward-compat — the current
    pipeline always regenerates because the conversation cards do not
    yet carry per-panel "image already exists" state. A future revision
    can short-circuit panels whose ``temp_image_url`` is already a valid
    MinIO key.
    """
    warnings: List[str] = []
    if not conversation_id:
        return {
            "panels": [],
            "warnings": ["conversation_id required to read panel cards"],
            "panel_count": 0,
            "success_count": 0,
            "error": "conversation_id required",
        }

    from app.models.conversation_message import ConversationMessage

    msgs = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at.asc())
        .all()
    )

    art_style: Dict[str, str] = {
        "base_style": "", "color_tone": "", "atmosphere": "",
    }
    characters: List[Dict[str, Any]] = []
    scenes: List[Dict[str, Any]] = []
    panels: List[Dict[str, Any]] = []

    for msg in msgs:
        entities = getattr(msg, "entities_json", None) or {}
        if not isinstance(entities, dict):
            continue
        card = entities.get("card")
        if not isinstance(card, dict):
            continue
        ctype = card.get("type")

        if ctype == "art_style":
            # Latest wins.
            art_style = {
                "base_style": str(card.get("base_style") or ""),
                "color_tone": str(card.get("color_tone") or ""),
                "atmosphere": str(card.get("atmosphere") or ""),
            }
        elif ctype == "characters" and not characters:
            for c in (card.get("characters") or []):
                if isinstance(c, dict) and c.get("name"):
                    characters.append(c)
        elif ctype == "scenes" and not scenes:
            for s in (card.get("scenes") or []):
                if isinstance(s, dict) and s.get("name"):
                    scenes.append(s)
        elif (
            ctype == "panels"
            and card.get("episode_number") == episode_number
            and not panels
        ):
            for p in (card.get("panels") or []):
                if isinstance(p, dict) and p.get("id"):
                    panels.append(p)

    if not panels:
        return {
            "panels": [],
            "warnings": [
                f"no panels card found for episode {episode_number} in "
                f"conversation {conversation_id}"
            ],
            "panel_count": 0,
            "success_count": 0,
        }

    results = await generate_panel_images_for_payload(
        episode_number=episode_number,
        project_id=project_id,
        art_style=art_style,
        characters=characters,
        scenes=scenes,
        panels=panels,
    )

    # Persist updated panels card (now with image keys) so a follow-up
    # commit_to_studio call can read fresh URLs.
    try:
        write_panels_card(
            db,
            conversation_id=conversation_id,
            episode_number=episode_number,
            panel_inputs=panels,
            results=results,
        )
        db.commit()
    except Exception as e:  # noqa: BLE001 — best-effort; never block return
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        warnings.append(f"panels card upsert failed: {e!r}")

    success_count = sum(1 for r in results if r.status == "success")
    return {
        "panels": [
            {
                "id": r.id,
                "image_url": r.image_url,
                "status": r.status,
                "error": r.error,
            }
            for r in results
        ],
        "warnings": warnings,
        "panel_count": len(results),
        "success_count": success_count,
    }
