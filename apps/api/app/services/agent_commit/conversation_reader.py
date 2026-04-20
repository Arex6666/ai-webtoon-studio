"""Reconstruct AgentCommit payload from ConversationMessage.entities_json cards.

If the frontend sends a lean payload ({conversation_id, episode_number, [title, summary]}),
this service scans messages in that conversation and extracts agent data for the target episode.

Card-type strings used here (`"panels"`, `"characters"`, `"scenes"`, `"art_style"`) are the
B1 agent-studio-bridge conventions — introduced for this lean commit flow. Frontend Task 14
will write these cards into ConversationMessage.entities_json during the episode pipeline.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.schemas.agent_commit import (
    AgentArtStyle,
    AgentCharacter,
    AgentPanel,
    AgentScene,
    CommitToStudioRequest,
)

logger = logging.getLogger(__name__)


def _extract_card(msg) -> Optional[Dict]:
    """Pull the card payload out of a message's entities_json."""
    entities = getattr(msg, "entities_json", None) or {}
    if not isinstance(entities, dict):
        return None
    card = entities.get("card")
    if isinstance(card, dict):
        return card
    return None


def enrich_request_from_conversation(
    db: Session,
    req: CommitToStudioRequest,
) -> Tuple[CommitToStudioRequest, List[str]]:
    """Return (possibly augmented request, warnings).

    Only fills fields that are empty in the request. Panels extracted from the first
    matching `panels` card whose `episode_number` matches. Characters/scenes from the
    first `characters`/`scenes` cards in the conversation. art_style from the latest
    `art_style` card.
    """
    from app.models.conversation_message import ConversationMessage  # lazy import

    warnings: List[str] = []

    # Skip enrichment entirely if request is already full.
    needs_panels = len(req.panels) == 0
    needs_chars = len(req.characters) == 0
    needs_scenes = len(req.scenes) == 0
    needs_style = (
        req.art_style.base_style == ""
        and req.art_style.color_tone == ""
        and req.art_style.atmosphere == ""
    )

    if not (needs_panels or needs_chars or needs_scenes or needs_style):
        return req, warnings

    messages = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == req.conversation_id)
        .order_by(ConversationMessage.created_at.asc())
        .all()
    )

    panels: List[AgentPanel] = []
    characters: List[AgentCharacter] = []
    scenes: List[AgentScene] = []
    art_style = req.art_style

    for msg in messages:
        card = _extract_card(msg)
        if not card:
            continue
        ctype = card.get("type")

        if (
            needs_panels
            and ctype == "panels"
            and card.get("episode_number") == req.episode_number
            and not panels  # only take first matching panels card
        ):
            raw_panels = card.get("panels", []) or []
            for i, p in enumerate(raw_panels):
                if not isinstance(p, dict):
                    continue
                try:
                    panels.append(
                        AgentPanel(
                            id=str(p.get("id") or f"conv-panel-{i}"),
                            order=int(p.get("order") if p.get("order") is not None else i),
                            scene_name=p.get("scene_name") or p.get("scene"),
                            characters=list(p.get("characters") or []),
                            scene_description=p.get("scene_description")
                            or p.get("description")
                            or "",
                            dialogue=p.get("dialogue"),
                            shot_type=p.get("shot_type") or "MS",
                            camera_angle=p.get("camera_angle") or "eye-level",
                            emotion=p.get("emotion"),
                            composition=p.get("composition"),
                            temp_image_url=p.get("temp_image_url") or p.get("image_url"),
                        )
                    )
                except Exception as e:  # pragma: no cover - defensive
                    warnings.append(f"conversation panel #{i} skipped: {e}")

        if needs_chars and ctype == "characters" and not characters:
            raw = card.get("characters", []) or []
            for c in raw:
                if not isinstance(c, dict) or not c.get("name"):
                    continue
                try:
                    characters.append(
                        AgentCharacter(
                            name=str(c["name"]),
                            visual_prompt=c.get("visual_prompt"),
                            temp_image_url=c.get("temp_image_url") or c.get("image_url"),
                            appearance_traits=list(c.get("appearance_traits") or []),
                            personality_traits=list(c.get("personality_traits") or []),
                            wardrobe_notes=c.get("wardrobe_notes"),
                        )
                    )
                except Exception as e:  # pragma: no cover - defensive
                    warnings.append(f"conversation character skipped: {e}")

        if needs_scenes and ctype == "scenes" and not scenes:
            raw = card.get("scenes", []) or []
            for s in raw:
                if not isinstance(s, dict) or not s.get("name"):
                    continue
                try:
                    scenes.append(
                        AgentScene(
                            name=str(s["name"]),
                            visual_prompt=s.get("visual_prompt"),
                            temp_image_url=s.get("temp_image_url") or s.get("image_url"),
                            time_of_day=s.get("time_of_day"),
                            weather=s.get("weather"),
                            mood=s.get("mood"),
                        )
                    )
                except Exception as e:  # pragma: no cover - defensive
                    warnings.append(f"conversation scene skipped: {e}")

        if needs_style and ctype == "art_style":
            # Keep overwriting so we land on the latest card in chronological order.
            art_style = AgentArtStyle(
                base_style=str(card.get("base_style") or ""),
                color_tone=str(card.get("color_tone") or ""),
                atmosphere=str(card.get("atmosphere") or ""),
            )

    enriched = req.model_copy(
        update={
            "panels": panels if needs_panels and panels else req.panels,
            "characters": characters if needs_chars and characters else req.characters,
            "scenes": scenes if needs_scenes and scenes else req.scenes,
            "art_style": art_style,
        }
    )
    return enriched, warnings
