"""Pure helpers: AgentPanel → Panel.spec_json, chapter source metadata."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict

from app.schemas.agent_commit import AgentPanel, AgentArtStyle


def build_panel_spec(
    panel: AgentPanel,
    *,
    panel_id: str,
    character_name_to_id: Dict[str, str],
    scene_name_to_id: Dict[str, str],
    art_style: AgentArtStyle,
) -> Dict[str, Any]:
    """Return a PanelSpec-shaped dict compatible with Cluster A writes."""
    scene_asset_id = scene_name_to_id.get(panel.scene_name) if panel.scene_name else None

    spec: Dict[str, Any] = {
        "id": panel_id,
        "index": panel.order,
        "shot": {
            "shotType": (panel.shot_type or "MS").upper(),
            "cameraAngle": panel.camera_angle or "eye-level",
            "durationSec": 3.0,
            "description": panel.scene_description or "",
            "composition": panel.composition or "",
        },
        "scene": {
            "location": panel.scene_name or "",
            "timeOfDay": "",
            "weather": "",
            "mood": panel.emotion or "",
        },
        "characters": [
            {"name": name, "asset_id": character_name_to_id[name]}
            if name in character_name_to_id else {"name": name}
            for name in panel.characters
        ],
        "dialogue": {
            "lines": ([{"speaker": "Unknown", "text": panel.dialogue, "type": "speech"}]
                      if panel.dialogue else []),
        },
        "style": {
            "styleProfileId": "default",
            "negativePrompt": "",
            "artStyleHint": f"{art_style.base_style}, {art_style.color_tone}, {art_style.atmosphere}".strip(", "),
        },
        "render": {"status": "Draft", "lastRenderAt": None, "warnings": []},
        "meta": {
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "source": "agent",
            "agent_panel_id": panel.id,
        },
    }

    if scene_asset_id:
        spec["scene"]["anchor_id"] = scene_asset_id

    return spec


def build_chapter_source(
    *,
    conversation_id: str,
    episode_number: int,
    art_style: AgentArtStyle,
) -> Dict[str, Any]:
    return {
        "type": "agent",
        "conversation_id": conversation_id,
        "episode_number": episode_number,
        "committed_at": datetime.now(timezone.utc).isoformat(),
        "art_style_snapshot": art_style.model_dump(),
    }
