"""
Cleanup duplicate/verbose scene assets and normalize chapter assets_lock scenes.

Usage:
  python scripts/cleanup_scene_assets.py --project-id <PROJECT_ID>            # dry-run
  python scripts/cleanup_scene_assets.py --project-id <PROJECT_ID> --apply
  python scripts/cleanup_scene_assets.py --project-id <PROJECT_ID> --apply --delete-duplicates
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.asset import Asset
from app.models.chapter import Chapter
from app.services.asset_name_extractor import sanitize_scene_name


@dataclass
class GroupPlan:
    canonical_name: str
    keeper: Asset
    losers: List[Asset]


def _canonical_scene_name(name: str) -> str:
    normalized = sanitize_scene_name(name)
    return normalized or name.strip()


def _pick_keeper(assets: List[Asset], canonical_name: str) -> Asset:
    exact = [a for a in assets if a.name.strip() == canonical_name]
    if exact:
        exact.sort(key=lambda a: (a.created_at or 0, len(a.name or "")))
        return exact[0]
    # Prefer shorter name; shorter scene names are usually canonical
    return sorted(assets, key=lambda a: (len(a.name or ""), a.created_at or 0))[0]


def build_merge_plan(db: Session, project_id: str | None) -> List[GroupPlan]:
    query = db.query(Asset).filter(Asset.type == "scene")
    if project_id:
        query = query.filter(Asset.project_id == project_id)
    assets = query.all()

    groups: Dict[Tuple[str, str], List[Asset]] = {}
    for asset in assets:
        canonical = _canonical_scene_name(asset.name or "")
        key = (asset.project_id, canonical)
        groups.setdefault(key, []).append(asset)

    plans: List[GroupPlan] = []
    for (_project_id, canonical), group_assets in groups.items():
        keeper = _pick_keeper(group_assets, canonical)
        losers = [a for a in group_assets if a.id != keeper.id]
        # Also normalize keeper name when it's verbose
        if losers or keeper.name != canonical:
            plans.append(GroupPlan(canonical_name=canonical, keeper=keeper, losers=losers))
    return plans


def _normalize_chapter_assets_lock(chapter: Chapter, keeper_map: Dict[str, Tuple[str, str]]) -> bool:
    """
    keeper_map: loser_asset_id -> (keeper_asset_id, canonical_scene_name)
    """
    lock = chapter.assets_lock_json or {}
    scenes = lock.get("scenes") or {}
    if not isinstance(scenes, dict):
        return False

    changed = False
    new_scenes = dict(scenes)
    for scene_id, scene_lock in list(scenes.items()):
        target_id = scene_id
        canonical_name = None
        if scene_id in keeper_map:
            target_id, canonical_name = keeper_map[scene_id]

        current_name = (scene_lock or {}).get("name", "")
        normalized_name = sanitize_scene_name(current_name) or current_name
        if canonical_name:
            normalized_name = canonical_name

        # move to keeper id
        if target_id != scene_id:
            changed = True
            existing = new_scenes.get(target_id) or {}
            merged = dict(scene_lock or {})
            merged.update(existing)
            merged["asset_id"] = target_id
            if normalized_name:
                merged["name"] = normalized_name
            new_scenes[target_id] = merged
            new_scenes.pop(scene_id, None)
            continue

        # same id but normalize name
        if normalized_name and normalized_name != current_name:
            changed = True
            entry = dict(scene_lock or {})
            entry["name"] = normalized_name
            new_scenes[scene_id] = entry

    if changed:
        new_lock = dict(lock)
        new_lock["scenes"] = new_scenes
        chapter.assets_lock_json = new_lock
    return changed


def apply_plan(
    db: Session,
    plans: List[GroupPlan],
    apply_changes: bool,
    delete_duplicates: bool,
    project_id: str | None,
) -> dict:
    keeper_map: Dict[str, Tuple[str, str]] = {}
    for plan in plans:
        for loser in plan.losers:
            keeper_map[loser.id] = (plan.keeper.id, plan.canonical_name)

    chapter_query = db.query(Chapter)
    if project_id:
        chapter_query = chapter_query.filter(Chapter.project_id == project_id)
    chapters = chapter_query.all()

    chapter_updates = 0
    for chapter in chapters:
        if _normalize_chapter_assets_lock(chapter, keeper_map):
            chapter_updates += 1

    renamed_keepers = 0
    merged_assets = 0
    deleted_assets = 0
    for plan in plans:
        keeper = plan.keeper
        if keeper.name != plan.canonical_name:
            renamed_keepers += 1
            if apply_changes:
                keeper.name = plan.canonical_name

        for loser in plan.losers:
            merged_assets += 1
            if not apply_changes:
                continue
            if delete_duplicates:
                db.delete(loser)
                deleted_assets += 1
            else:
                loser.status = "merged"
                data = dict(loser.data_json or {})
                data["merged_into"] = keeper.id
                data["merged_canonical_name"] = plan.canonical_name
                loser.data_json = data

    if apply_changes:
        db.commit()

    return {
        "plans": len(plans),
        "chapters_touched": chapter_updates,
        "renamed_keepers": renamed_keepers,
        "merged_assets": merged_assets,
        "deleted_assets": deleted_assets,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Cleanup duplicate scene assets")
    parser.add_argument("--project-id", help="Only process one project", default=None)
    parser.add_argument("--apply", action="store_true", help="Apply changes")
    parser.add_argument("--delete-duplicates", action="store_true", help="Delete loser assets (only with --apply)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        plans = build_merge_plan(db, args.project_id)
        report = apply_plan(
            db=db,
            plans=plans,
            apply_changes=args.apply,
            delete_duplicates=args.delete_duplicates and args.apply,
            project_id=args.project_id,
        )

        preview = []
        for p in plans[:20]:
            preview.append(
                {
                    "canonical": p.canonical_name,
                    "keeper": {"id": p.keeper.id, "name": p.keeper.name},
                    "losers": [{"id": a.id, "name": a.name} for a in p.losers],
                }
            )

        print(
            json.dumps(
                {
                    "mode": "apply" if args.apply else "dry-run",
                    "project_id": args.project_id,
                    "report": report,
                    "preview_first_20": preview,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()

