"""Upsert Asset records from agent character/scene payload with optional image persistence."""
from __future__ import annotations

import logging
import uuid
from typing import Dict, List, Tuple

from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.schemas.agent_commit import AgentCharacter, AgentScene
from app.services.agent_commit.image_fetcher import fetch_and_persist, ImageFetchError

logger = logging.getLogger(__name__)


async def sync_character(
    db: Session,
    project_id: str,
    character: AgentCharacter,
    *,
    source_conversation_id: str,
) -> Tuple[str, List[str]]:
    """Returns (asset_id, warnings). Creates or reuses a character Asset."""
    warnings: List[str] = []
    existing = (
        db.query(Asset)
        .filter(Asset.project_id == project_id, Asset.type == "character", Asset.name == character.name)
        .first()
    )
    if existing:
        return existing.id, warnings

    asset_id = str(uuid.uuid4())
    data_json: Dict = {
        "appearance_traits": character.appearance_traits,
        "personality_traits": character.personality_traits,
        "wardrobe_notes": character.wardrobe_notes or "",
        "visual_prompt": character.visual_prompt or "",
        "created_via": "agent",
        "source_conversation_id": source_conversation_id,
    }

    thumbnail_url = None
    if character.temp_image_url:
        try:
            thumbnail_url = await fetch_and_persist(
                character.temp_image_url,
                project_id=project_id,
                asset_type="character",
                name_hint=character.name,
            )
        except ImageFetchError as e:
            warnings.append(f"character '{character.name}' reference image failed: {e}")

    asset = Asset(
        id=asset_id,
        project_id=project_id,
        type="character",
        name=character.name,
        description=character.visual_prompt or "",
        thumbnail_url=thumbnail_url,
        data_json=data_json,
    )
    db.add(asset)
    db.flush()
    return asset_id, warnings


async def sync_scene(
    db: Session,
    project_id: str,
    scene: AgentScene,
    *,
    source_conversation_id: str,
) -> Tuple[str, List[str]]:
    warnings: List[str] = []
    existing = (
        db.query(Asset)
        .filter(Asset.project_id == project_id, Asset.type == "scene", Asset.name == scene.name)
        .first()
    )
    if existing:
        return existing.id, warnings

    asset_id = str(uuid.uuid4())
    data_json: Dict = {
        "time_of_day": scene.time_of_day or "",
        "weather": scene.weather or "",
        "mood": scene.mood or "",
        "visual_prompt": scene.visual_prompt or "",
        "created_via": "agent",
        "source_conversation_id": source_conversation_id,
    }

    thumbnail_url = None
    if scene.temp_image_url:
        try:
            thumbnail_url = await fetch_and_persist(
                scene.temp_image_url,
                project_id=project_id,
                asset_type="scene",
                name_hint=scene.name,
            )
        except ImageFetchError as e:
            warnings.append(f"scene '{scene.name}' reference image failed: {e}")

    asset = Asset(
        id=asset_id,
        project_id=project_id,
        type="scene",
        name=scene.name,
        description=scene.visual_prompt or "",
        thumbnail_url=thumbnail_url,
        data_json=data_json,
    )
    db.add(asset)
    db.flush()
    return asset_id, warnings
