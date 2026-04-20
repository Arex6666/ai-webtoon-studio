"""Apply panel-level bindings and keep ChapterBindings aggregate in sync."""
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.models.panel import Panel
from app.models.bindings import ChapterBindings
from app.models.asset import Asset


def apply_panel_binding(
    spec_json: Dict[str, Any],
    slot: str,
    slot_index: int,
    asset_id: Optional[str],
    asset_version_id: Optional[str],
) -> Dict[str, Any]:
    """Return a NEW spec_json dict with the binding applied. Pure function."""
    spec = {**(spec_json or {})}

    if slot == "character":
        characters = list(spec.get("characters", []))
        while len(characters) <= slot_index:
            characters.append({})
        entry = characters[slot_index]
        if isinstance(entry, str):
            entry = {"name": entry}
        elif not isinstance(entry, dict):
            entry = {}
        else:
            entry = {**entry}
        if asset_id is None:
            entry.pop("asset_id", None)
            entry.pop("asset_version_id", None)
        else:
            entry["asset_id"] = asset_id
            if asset_version_id:
                entry["asset_version_id"] = asset_version_id
            else:
                entry.pop("asset_version_id", None)
        characters[slot_index] = entry
        spec["characters"] = characters
        return spec

    if slot == "scene":
        scene = {**(spec.get("scene") or {})}
        if asset_id is None:
            scene.pop("anchor_id", None)
        else:
            scene["anchor_id"] = asset_id
        spec["scene"] = scene
        return spec

    if slot == "prop":
        props = list(spec.get("props", []))
        while len(props) <= slot_index:
            props.append({})
        entry = props[slot_index] if isinstance(props[slot_index], dict) else {}
        entry = {**entry}
        if asset_id is None:
            entry.pop("asset_id", None)
        else:
            entry["asset_id"] = asset_id
        props[slot_index] = entry
        spec["props"] = props
        return spec

    raise ValueError(f"Unknown slot: {slot}")


def refresh_chapter_bindings(db: Session, chapter_id: str) -> ChapterBindings:
    """Recompute ChapterBindings aggregate from all panels in the chapter.

    Returns the updated (or newly created) ChapterBindings row. Commits.
    """
    panels = db.query(Panel).filter(Panel.chapter_id == chapter_id).all()

    identity_ids: set[str] = set()
    scene_ids: set[str] = set()
    anchor_ids: set[str] = set()

    for p in panels:
        spec = p.spec_json or {}
        for c in spec.get("characters", []) or []:
            if isinstance(c, dict) and c.get("asset_id"):
                identity_ids.add(c["asset_id"])
        anchor = (spec.get("scene") or {}).get("anchor_id")
        if anchor:
            scene_ids.add(anchor)
            anchor_ids.add(anchor)

    bindings = (
        db.query(ChapterBindings)
        .filter(ChapterBindings.chapter_id == chapter_id)
        .first()
    )
    if not bindings:
        import uuid as _uuid

        bindings = ChapterBindings(
            id=str(_uuid.uuid4()), chapter_id=chapter_id
        )
        db.add(bindings)

    bindings.identity_asset_ids = sorted(identity_ids)
    bindings.scene_asset_ids = sorted(scene_ids)
    bindings.anchor_ids = sorted(anchor_ids)
    db.commit()
    db.refresh(bindings)
    return bindings


def get_asset_or_raise(db: Session, asset_id: str, expected_type: str) -> Asset:
    """Load asset and validate type. Raises ValueError on mismatch, LookupError on 404."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise LookupError(f"Asset {asset_id} not found")
    # character/scene/prop must map 1:1 to Asset.type
    if asset.type != expected_type:
        raise ValueError(
            f"Asset {asset_id} has type '{asset.type}', expected '{expected_type}'"
        )
    return asset
