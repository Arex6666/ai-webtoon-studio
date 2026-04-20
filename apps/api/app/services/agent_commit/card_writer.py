"""Build ConversationMessage entries carrying agent-output cards.

Supports four card types: panels, characters, scenes, art_style. The writer is
idempotent at the (conversation_id, card_type, episode_number) granularity: if a
matching card already exists it is updated in place rather than duplicated.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.conversation_message import ConversationMessage

logger = logging.getLogger(__name__)


CARD_TYPE_PANELS = "panels"
CARD_TYPE_CHARACTERS = "characters"
CARD_TYPE_SCENES = "scenes"
CARD_TYPE_ART_STYLE = "art_style"


def _matches_card(
    msg: ConversationMessage,
    card_type: str,
    episode_number: Optional[int],
) -> bool:
    entities = getattr(msg, "entities_json", None) or {}
    card = entities.get("card") if isinstance(entities, dict) else None
    if not isinstance(card, dict):
        return False
    if card.get("type") != card_type:
        return False
    if episode_number is None:
        return True
    return card.get("episode_number") == episode_number


def upsert_card(
    db: Session,
    conversation_id: str,
    card_type: str,
    card_data: Dict[str, Any],
    *,
    episode_number: Optional[int] = None,
    content_text: Optional[str] = None,
) -> ConversationMessage:
    """Upsert a card message. Returns the persisted message.

    If card_type is `panels` the caller MUST pass episode_number so we can
    discriminate between episodes. For characters/scenes/art_style, caller
    may omit episode_number (treated as conversation-wide).
    """
    existing_msgs = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at.asc())
        .all()
    )
    existing = next(
        (m for m in existing_msgs if _matches_card(m, card_type, episode_number)),
        None,
    )

    card_payload: Dict[str, Any] = {"type": card_type, **card_data}
    if episode_number is not None:
        card_payload["episode_number"] = episode_number

    entities = {"card": card_payload}
    content = content_text or f"[{card_type}]"

    if existing is not None:
        existing.entities_json = entities
        existing.content = content
        db.flush()
        return existing

    msg = ConversationMessage(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role="assistant",
        content=content,
        entities_json=entities,
    )
    db.add(msg)
    db.flush()
    return msg


def build_characters_card(characters: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract only the fields conversation_reader needs."""
    return {
        "characters": [
            {
                "name": c.get("name"),
                "visual_prompt": c.get("visual_prompt"),
                "temp_image_url": c.get("image_url") or c.get("temp_image_url"),
                "appearance_traits": c.get("appearance_traits") or [],
                "personality_traits": c.get("personality_traits") or [],
                "wardrobe_notes": c.get("wardrobe_notes"),
            }
            for c in (characters or [])
            if c and c.get("name")
        ],
    }


def build_scenes_card(scenes: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "scenes": [
            {
                "name": s.get("name"),
                "visual_prompt": s.get("visual_prompt"),
                "temp_image_url": s.get("image_url") or s.get("temp_image_url"),
                "time_of_day": s.get("time_of_day"),
                "weather": s.get("weather"),
                "mood": s.get("mood"),
            }
            for s in (scenes or [])
            if s and s.get("name")
        ],
    }


def build_panels_card(panels: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "panels": [
            {
                "id": p.get("id"),
                "order": p.get("order", p.get("index", 0)),
                "scene_name": p.get("scene_name"),
                "characters": p.get("characters") or [],
                "scene_description": p.get("scene_description") or p.get("description") or "",
                "dialogue": p.get("dialogue"),
                "shot_type": p.get("shot_type") or "MS",
                "camera_angle": p.get("camera_angle") or "eye-level",
                "emotion": p.get("emotion"),
                "composition": p.get("composition"),
                "temp_image_url": p.get("image_url") or p.get("temp_image_url"),
            }
            for p in (panels or [])
            if p and p.get("id")
        ],
    }


def build_art_style_card(
    base_style: str = "",
    color_tone: str = "",
    atmosphere: str = "",
) -> Dict[str, Any]:
    return {
        "base_style": base_style,
        "color_tone": color_tone,
        "atmosphere": atmosphere,
    }
