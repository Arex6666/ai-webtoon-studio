# Cluster A — Studio Main-Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the Studio script→storyboard→asset loop by adding panel-level binding PATCH, unifying ScriptInput onto `/chapters/{id}/storyboard`, and shipping the asset edit Drawer.

**Architecture:**
- Backend: one new panel-bindings endpoint (mutates `panel.spec_json` and refreshes `ChapterBindings` in a single transaction); one asset-usage query endpoint. No DDL.
- Frontend: wire three existing TODOs (AssetsTab `:634`/`:705`, ScriptInput `:83`, assets/page `:534`) to the above endpoints; build a Sheet-based `AssetEditDrawer` with Basic/Traits/Versions/Usage tabs.
- Contract: both features reuse the existing `/chapters/{id}/storyboard` flow and `panel.spec_json` as single source of truth.

**Tech Stack:** FastAPI + SQLAlchemy + Pydantic v2 (backend); Next.js 14 + TanStack Query + Zustand + shadcn/ui Sheet (frontend); pytest for backend; manual + Playwright-optional for frontend.

**Spec:** `docs/superpowers/specs/2026-04-20-cluster-a-main-loop-design.md`

---

## File Structure

### Backend
```
apps/api/app/
├── api/routes/panels.py                          MODIFY  — add PATCH /{panel_id}/bindings
├── api/routes/assets/__init__.py                 MODIFY  — mount new usage route
├── api/routes/assets/usage.py                    CREATE  — GET /{asset_id}/usage
├── services/binding/                             CREATE  — new package
│   ├── __init__.py                               CREATE
│   └── binding_service.py                        CREATE  — apply_panel_binding + refresh_chapter_bindings
└── schemas/panel_bindings.py                     CREATE  — Pydantic req/resp

apps/api/tests/unit/routes/
├── test_panel_bindings.py                        CREATE
└── test_asset_usage.py                           CREATE
```

### Frontend
```
apps/web/src/
├── lib/api/services.ts                           MODIFY  — add panelsApi.updateBindings, assetsApi.getUsage
├── lib/store/studioStore.ts                      MODIFY  — add storyboardJob state slice
├── components/script-editor/ScriptInput.tsx      MODIFY  — state machine + handleConfirm
├── components/studio/right/AssetsTab.tsx         MODIFY  — wire :634, :705, add Clear button
├── components/assets/AssetEditDrawer.tsx         CREATE  — Sheet shell + tab switcher
├── components/assets/drawer/BasicTab.tsx         CREATE
├── components/assets/drawer/TraitsTab.tsx        CREATE
├── components/assets/drawer/VersionsTab.tsx      CREATE  — empty state only
├── components/assets/drawer/UsageTab.tsx         CREATE
└── app/assets/page.tsx                           MODIFY  — replace :534 TODO
```

---

## Task 1: Pydantic schemas for panel bindings

**Files:**
- Create: `apps/api/app/schemas/panel_bindings.py`

- [ ] **Step 1: Write the schema file**

```python
"""Panel binding request/response schemas."""
from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, Field


class PanelBindingPatch(BaseModel):
    """Request body for PATCH /panels/{panel_id}/bindings."""
    slot: Literal["character", "scene", "prop"] = Field(
        ..., description="Which slot in spec_json to update."
    )
    slot_index: int = Field(
        0,
        ge=0,
        description="Index into characters[]/props[]. Ignored for scene.",
    )
    asset_id: Optional[str] = Field(
        ..., description="Target asset id. null clears the binding."
    )
    asset_version_id: Optional[str] = Field(
        None, description="Optional version pin. Defaults to asset's current version."
    )


class PanelBindingResponse(BaseModel):
    panel_id: str
    spec_json: Dict[str, Any]
    chapter_bindings_updated: bool
```

- [ ] **Step 2: Verify import works**

Run: `cd apps/api && python -c "from app.schemas.panel_bindings import PanelBindingPatch, PanelBindingResponse; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/schemas/panel_bindings.py
git commit -m "feat(api): add panel binding pydantic schemas"
```

---

## Task 2: binding_service — pure functions for spec_json mutation

**Files:**
- Create: `apps/api/app/services/binding/__init__.py`
- Create: `apps/api/app/services/binding/binding_service.py`

- [ ] **Step 1: Create package init**

```python
"""Binding service — panel spec_json mutation + chapter bindings sync."""
from app.services.binding.binding_service import (
    apply_panel_binding,
    refresh_chapter_bindings,
)

__all__ = ["apply_panel_binding", "refresh_chapter_bindings"]
```

Write to `apps/api/app/services/binding/__init__.py`.

- [ ] **Step 2: Implement binding_service.py**

```python
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
```

Write to `apps/api/app/services/binding/binding_service.py`.

- [ ] **Step 3: Verify import**

Run: `cd apps/api && python -c "from app.services.binding import apply_panel_binding, refresh_chapter_bindings; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add apps/api/app/services/binding/
git commit -m "feat(api): add binding_service with pure apply + aggregate refresh"
```

---

## Task 3: Unit tests for apply_panel_binding (pure function)

**Files:**
- Create: `apps/api/tests/unit/services/__init__.py` (empty if missing)
- Create: `apps/api/tests/unit/services/test_binding_service.py`

- [ ] **Step 1: Ensure dir exists**

```bash
mkdir -p apps/api/tests/unit/services
touch apps/api/tests/unit/services/__init__.py
```

- [ ] **Step 2: Write failing tests**

```python
"""Unit tests for the pure apply_panel_binding function."""
import pytest

from app.services.binding.binding_service import apply_panel_binding


class TestApplyPanelBinding:
    def test_character_string_to_dict(self):
        spec = {"characters": ["Alice"]}
        out = apply_panel_binding(spec, "character", 0, "asset-1", None)
        assert out["characters"][0] == {"name": "Alice", "asset_id": "asset-1"}

    def test_character_dict_merge(self):
        spec = {"characters": [{"name": "Alice", "emotion": "happy"}]}
        out = apply_panel_binding(spec, "character", 0, "asset-1", "ver-9")
        assert out["characters"][0] == {
            "name": "Alice",
            "emotion": "happy",
            "asset_id": "asset-1",
            "asset_version_id": "ver-9",
        }

    def test_character_clear(self):
        spec = {"characters": [{"name": "Alice", "asset_id": "asset-1", "asset_version_id": "v"}]}
        out = apply_panel_binding(spec, "character", 0, None, None)
        assert out["characters"][0] == {"name": "Alice"}

    def test_character_extends_list(self):
        spec = {"characters": []}
        out = apply_panel_binding(spec, "character", 2, "asset-x", None)
        assert len(out["characters"]) == 3
        assert out["characters"][2] == {"asset_id": "asset-x"}

    def test_scene_sets_anchor(self):
        spec = {"scene": {"location": "rooftop"}}
        out = apply_panel_binding(spec, "scene", 0, "scene-1", None)
        assert out["scene"] == {"location": "rooftop", "anchor_id": "scene-1"}

    def test_scene_clear_anchor(self):
        spec = {"scene": {"location": "rooftop", "anchor_id": "scene-1"}}
        out = apply_panel_binding(spec, "scene", 0, None, None)
        assert out["scene"] == {"location": "rooftop"}

    def test_prop_binding(self):
        spec = {"props": [{"name": "sword"}]}
        out = apply_panel_binding(spec, "prop", 0, "prop-1", None)
        assert out["props"][0] == {"name": "sword", "asset_id": "prop-1"}

    def test_unknown_slot_raises(self):
        with pytest.raises(ValueError):
            apply_panel_binding({}, "bogus", 0, "a", None)

    def test_does_not_mutate_input(self):
        spec = {"characters": [{"name": "Alice"}]}
        _ = apply_panel_binding(spec, "character", 0, "asset-1", None)
        assert spec == {"characters": [{"name": "Alice"}]}
```

Write to `apps/api/tests/unit/services/test_binding_service.py`.

- [ ] **Step 3: Run tests**

Run: `cd apps/api && pytest tests/unit/services/test_binding_service.py -v`
Expected: all 9 PASS (implementation from Task 2 already in place)

- [ ] **Step 4: Commit**

```bash
git add apps/api/tests/unit/services/
git commit -m "test(api): cover apply_panel_binding pure function"
```

---

## Task 4: Add PATCH /panels/{id}/bindings endpoint

**Files:**
- Modify: `apps/api/app/api/routes/panels.py` (append near `PUT /{panel_id}/spec` which starts around `:241`)

- [ ] **Step 1: Add the endpoint**

Insert in `panels.py` right after the existing `PUT /{panel_id}/spec` route (before `/{panel_id}/order`). Use this exact block:

```python
from app.schemas.panel_bindings import PanelBindingPatch, PanelBindingResponse
from app.services.binding import (
    apply_panel_binding,
    refresh_chapter_bindings,
)
from app.services.binding.binding_service import get_asset_or_raise
from sqlalchemy.orm.attributes import flag_modified


@router.patch("/{panel_id}/bindings", response_model=PanelBindingResponse)
def patch_panel_bindings(
    panel_id: str,
    body: PanelBindingPatch,
    db: Session = Depends(get_db),
):
    """Update a single binding slot on a panel's spec_json.

    Slot='character'/'prop' use slot_index; slot='scene' ignores slot_index.
    asset_id=null clears the binding.
    """
    panel = db.query(Panel).filter(Panel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")

    if panel.render_status in ("queued", "running", "rendering"):
        raise HTTPException(
            status_code=409,
            detail="Panel is rendering; cannot modify bindings. Wait or cancel render first.",
        )

    if body.asset_id is not None:
        try:
            get_asset_or_raise(db, body.asset_id, body.slot)
        except LookupError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    new_spec = apply_panel_binding(
        panel.spec_json or {},
        body.slot,
        body.slot_index,
        body.asset_id,
        body.asset_version_id,
    )
    panel.spec_json = new_spec
    flag_modified(panel, "spec_json")
    db.commit()
    db.refresh(panel)

    refresh_chapter_bindings(db, panel.chapter_id)

    return PanelBindingResponse(
        panel_id=panel.id,
        spec_json=panel.spec_json,
        chapter_bindings_updated=True,
    )
```

- [ ] **Step 2: Verify route registered**

Run: `cd apps/api && python -c "from app.main import app; [print(r.methods, r.path) for r in app.routes if 'bindings' in r.path]"`
Expected output includes: `{'PATCH'} /api/v1/panels/{panel_id}/bindings`

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/api/routes/panels.py
git commit -m "feat(api): add PATCH /panels/{id}/bindings"
```

---

## Task 5: Integration tests for PATCH /panels/{id}/bindings

**Files:**
- Create: `apps/api/tests/unit/routes/test_panel_bindings.py`

- [ ] **Step 1: Write the tests**

```python
"""Integration tests for PATCH /api/v1/panels/{panel_id}/bindings."""
import uuid
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def seeded(test_client: TestClient):
    """Seed one project, chapter, panel, and one character + one scene asset."""
    import os
    os.environ["ENABLE_AUTH"] = "false"

    from app.main import app
    from app.core.database import SessionLocal
    from app.models.project import Project
    from app.models.chapter import Chapter
    from app.models.panel import Panel
    from app.models.asset import Asset

    db = SessionLocal()
    try:
        proj = Project(id=str(uuid.uuid4()), name="T", description="")
        db.add(proj)
        ch = Chapter(
            id=str(uuid.uuid4()),
            project_id=proj.id,
            chapter_number=1,
            title="ch1",
            script_raw="hi",
        )
        db.add(ch)
        panel = Panel(
            id=str(uuid.uuid4()),
            chapter_id=ch.id,
            order_index=0,
            spec_json={"characters": [{"name": "Alice"}], "scene": {"location": "rooftop"}},
            render_status="draft",
        )
        db.add(panel)
        char_asset = Asset(
            id=str(uuid.uuid4()),
            project_id=proj.id,
            type="character",
            name="Alice",
            data_json={},
        )
        scene_asset = Asset(
            id=str(uuid.uuid4()),
            project_id=proj.id,
            type="scene",
            name="Rooftop",
            data_json={},
        )
        db.add_all([char_asset, scene_asset])
        db.commit()
        return {
            "project_id": proj.id,
            "chapter_id": ch.id,
            "panel_id": panel.id,
            "char_asset_id": char_asset.id,
            "scene_asset_id": scene_asset.id,
        }
    finally:
        db.close()


class TestPatchPanelBindings:
    def test_bind_character_happy_path(self, test_client, seeded):
        resp = test_client.patch(
            f"/api/v1/panels/{seeded['panel_id']}/bindings",
            json={"slot": "character", "slot_index": 0, "asset_id": seeded["char_asset_id"]},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["chapter_bindings_updated"] is True
        assert body["spec_json"]["characters"][0]["asset_id"] == seeded["char_asset_id"]

    def test_bind_scene_anchor(self, test_client, seeded):
        resp = test_client.patch(
            f"/api/v1/panels/{seeded['panel_id']}/bindings",
            json={"slot": "scene", "slot_index": 0, "asset_id": seeded["scene_asset_id"]},
        )
        assert resp.status_code == 200
        assert resp.json()["spec_json"]["scene"]["anchor_id"] == seeded["scene_asset_id"]

    def test_clear_binding(self, test_client, seeded):
        test_client.patch(
            f"/api/v1/panels/{seeded['panel_id']}/bindings",
            json={"slot": "character", "slot_index": 0, "asset_id": seeded["char_asset_id"]},
        )
        resp = test_client.patch(
            f"/api/v1/panels/{seeded['panel_id']}/bindings",
            json={"slot": "character", "slot_index": 0, "asset_id": None},
        )
        assert resp.status_code == 200
        assert "asset_id" not in resp.json()["spec_json"]["characters"][0]

    def test_panel_not_found(self, test_client):
        resp = test_client.patch(
            "/api/v1/panels/bogus/bindings",
            json={"slot": "character", "slot_index": 0, "asset_id": "x"},
        )
        assert resp.status_code == 404

    def test_asset_type_mismatch(self, test_client, seeded):
        # Bind a scene asset into a character slot → 400
        resp = test_client.patch(
            f"/api/v1/panels/{seeded['panel_id']}/bindings",
            json={"slot": "character", "slot_index": 0, "asset_id": seeded["scene_asset_id"]},
        )
        assert resp.status_code == 400

    def test_asset_not_found(self, test_client, seeded):
        resp = test_client.patch(
            f"/api/v1/panels/{seeded['panel_id']}/bindings",
            json={"slot": "character", "slot_index": 0, "asset_id": "does-not-exist"},
        )
        assert resp.status_code == 404

    def test_rendering_returns_409(self, test_client, seeded):
        from app.core.database import SessionLocal
        from app.models.panel import Panel

        db = SessionLocal()
        try:
            p = db.query(Panel).filter(Panel.id == seeded["panel_id"]).first()
            p.render_status = "running"
            db.commit()
        finally:
            db.close()

        resp = test_client.patch(
            f"/api/v1/panels/{seeded['panel_id']}/bindings",
            json={"slot": "character", "slot_index": 0, "asset_id": seeded["char_asset_id"]},
        )
        assert resp.status_code == 409

    def test_chapter_bindings_aggregate_refreshed(self, test_client, seeded):
        from app.core.database import SessionLocal
        from app.models.bindings import ChapterBindings

        test_client.patch(
            f"/api/v1/panels/{seeded['panel_id']}/bindings",
            json={"slot": "character", "slot_index": 0, "asset_id": seeded["char_asset_id"]},
        )
        test_client.patch(
            f"/api/v1/panels/{seeded['panel_id']}/bindings",
            json={"slot": "scene", "slot_index": 0, "asset_id": seeded["scene_asset_id"]},
        )

        db = SessionLocal()
        try:
            cb = db.query(ChapterBindings).filter(
                ChapterBindings.chapter_id == seeded["chapter_id"]
            ).first()
            assert cb is not None
            assert seeded["char_asset_id"] in (cb.identity_asset_ids or [])
            assert seeded["scene_asset_id"] in (cb.scene_asset_ids or [])
        finally:
            db.close()
```

- [ ] **Step 2: Run tests**

Run: `cd apps/api && pytest tests/unit/routes/test_panel_bindings.py -v`
Expected: all 8 PASS

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/unit/routes/test_panel_bindings.py
git commit -m "test(api): cover PATCH /panels/{id}/bindings integration"
```

---

## Task 6: Push WS event on binding change

**Files:**
- Modify: `apps/api/app/api/routes/panels.py` (extend the endpoint added in Task 4)

- [ ] **Step 1: Add WS emit inside the endpoint**

Find the `refresh_chapter_bindings(db, panel.chapter_id)` line added in Task 4. Immediately after it, insert:

```python
try:
    from app.api.routes.ws import push_unified_job_event
    import anyio

    async def _emit():
        await push_unified_job_event(
            panel.chapter_id,
            "panel_binding_updated",
            panel.id,
            {
                "panel_id": panel.id,
                "slot": body.slot,
                "slot_index": body.slot_index,
                "asset_id": body.asset_id,
            },
        )

    anyio.from_thread.run(_emit)
except Exception as e:  # noqa: BLE001
    import logging
    logging.getLogger(__name__).warning(f"WS emit failed: {e}")
```

If the surrounding function is already `async`, drop the `anyio.from_thread.run` shim and `await _emit()` directly. Confirm by looking at the function's `def` line — if it reads `def patch_panel_bindings`, keep the shim; if `async def`, simplify.

- [ ] **Step 2: Re-run panel binding tests (WS emit must not break them)**

Run: `cd apps/api && pytest tests/unit/routes/test_panel_bindings.py -v`
Expected: all 8 still PASS (WS failure is swallowed)

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/api/routes/panels.py
git commit -m "feat(api): emit panel_binding_updated WS event on binding change"
```

---

## Task 7: Add GET /api/v1/assets/{id}/usage

**Files:**
- Create: `apps/api/app/api/routes/assets/usage.py`
- Modify: `apps/api/app/api/routes/assets/__init__.py`

- [ ] **Step 1: Write the route file**

```python
"""Asset usage lookup — where a given asset is referenced."""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.asset import Asset
from app.models.chapter import Chapter
from app.models.panel import Panel

router = APIRouter()


class UsageReference(BaseModel):
    chapter_id: str
    chapter_title: Optional[str]
    panel_id: str
    panel_order: int
    panel_preview_url: Optional[str] = None


class AssetUsageResponse(BaseModel):
    asset_id: str
    references: List[UsageReference]
    total_count: int


def _panel_references_asset(spec: Dict[str, Any], asset_id: str) -> bool:
    for c in (spec.get("characters") or []):
        if isinstance(c, dict) and c.get("asset_id") == asset_id:
            return True
    if (spec.get("scene") or {}).get("anchor_id") == asset_id:
        return True
    for p in (spec.get("props") or []):
        if isinstance(p, dict) and p.get("asset_id") == asset_id:
            return True
    return False


@router.get("/{asset_id}/usage", response_model=AssetUsageResponse)
def get_asset_usage(
    asset_id: str,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Candidate chapters scoped by asset's project
    chapters = (
        db.query(Chapter).filter(Chapter.project_id == asset.project_id).all()
    )
    chapter_ids = [c.id for c in chapters]
    chapter_title_by_id = {c.id: c.title for c in chapters}

    panels = (
        db.query(Panel)
        .filter(Panel.chapter_id.in_(chapter_ids))
        .order_by(Panel.chapter_id, Panel.order_index)
        .all()
    )

    refs: List[UsageReference] = []
    for p in panels:
        if _panel_references_asset(p.spec_json or {}, asset_id):
            refs.append(
                UsageReference(
                    chapter_id=p.chapter_id,
                    chapter_title=chapter_title_by_id.get(p.chapter_id),
                    panel_id=p.id,
                    panel_order=p.order_index or 0,
                    panel_preview_url=p.preview_url,
                )
            )

    return AssetUsageResponse(
        asset_id=asset_id,
        references=refs[:limit],
        total_count=len(refs),
    )
```

Write to `apps/api/app/api/routes/assets/usage.py`.

- [ ] **Step 2: Mount the router**

Open `apps/api/app/api/routes/assets/__init__.py` and append (or add near the other `include_router` calls):

```python
from app.api.routes.assets import usage as _usage_module
router.include_router(_usage_module.router, tags=["assets"])
```

If the file uses a different pattern (e.g., explicit import list), follow the existing style — but ensure the `usage.router` is mounted under `/api/v1/assets`.

- [ ] **Step 3: Verify route registered**

Run: `cd apps/api && python -c "from app.main import app; [print(r.methods, r.path) for r in app.routes if 'usage' in r.path]"`
Expected: `{'GET'} /api/v1/assets/{asset_id}/usage`

- [ ] **Step 4: Commit**

```bash
git add apps/api/app/api/routes/assets/
git commit -m "feat(api): add GET /assets/{id}/usage for asset reference lookup"
```

---

## Task 8: Tests for asset usage endpoint

**Files:**
- Create: `apps/api/tests/unit/routes/test_asset_usage.py`

- [ ] **Step 1: Write the tests**

```python
"""Integration tests for GET /api/v1/assets/{asset_id}/usage."""
import uuid
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def seeded_usage(test_client: TestClient):
    import os
    os.environ["ENABLE_AUTH"] = "false"

    from app.core.database import SessionLocal
    from app.models.project import Project
    from app.models.chapter import Chapter
    from app.models.panel import Panel
    from app.models.asset import Asset

    db = SessionLocal()
    try:
        proj = Project(id=str(uuid.uuid4()), name="UP", description="")
        db.add(proj)
        ch = Chapter(
            id=str(uuid.uuid4()),
            project_id=proj.id,
            chapter_number=1,
            title="Ep1",
            script_raw="",
        )
        db.add(ch)
        asset = Asset(
            id=str(uuid.uuid4()),
            project_id=proj.id,
            type="character",
            name="Hero",
            data_json={},
        )
        db.add(asset)

        used_panel = Panel(
            id=str(uuid.uuid4()),
            chapter_id=ch.id,
            order_index=0,
            spec_json={"characters": [{"name": "Hero", "asset_id": asset.id}]},
        )
        unused_panel = Panel(
            id=str(uuid.uuid4()),
            chapter_id=ch.id,
            order_index=1,
            spec_json={"characters": [{"name": "Other"}]},
        )
        db.add_all([used_panel, unused_panel])
        db.commit()
        return {
            "asset_id": asset.id,
            "used_panel_id": used_panel.id,
            "unused_panel_id": unused_panel.id,
            "chapter_id": ch.id,
        }
    finally:
        db.close()


class TestAssetUsage:
    def test_returns_referring_panels(self, test_client, seeded_usage):
        resp = test_client.get(f"/api/v1/assets/{seeded_usage['asset_id']}/usage")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_count"] == 1
        assert body["references"][0]["panel_id"] == seeded_usage["used_panel_id"]
        assert body["references"][0]["chapter_id"] == seeded_usage["chapter_id"]

    def test_asset_not_found(self, test_client):
        resp = test_client.get("/api/v1/assets/does-not-exist/usage")
        assert resp.status_code == 404

    def test_no_references(self, test_client):
        import uuid as _u
        from app.core.database import SessionLocal
        from app.models.project import Project
        from app.models.asset import Asset

        db = SessionLocal()
        try:
            proj = Project(id=str(_u.uuid4()), name="X", description="")
            db.add(proj)
            orphan = Asset(
                id=str(_u.uuid4()),
                project_id=proj.id,
                type="character",
                name="Orphan",
                data_json={},
            )
            db.add(orphan)
            db.commit()
            asset_id = orphan.id
        finally:
            db.close()

        resp = test_client.get(f"/api/v1/assets/{asset_id}/usage")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_count"] == 0
        assert body["references"] == []
```

- [ ] **Step 2: Run tests**

Run: `cd apps/api && pytest tests/unit/routes/test_asset_usage.py -v`
Expected: all 3 PASS

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/unit/routes/test_asset_usage.py
git commit -m "test(api): cover GET /assets/{id}/usage"
```

---

## Task 9: Frontend — add panelsApi.updateBindings + assetsApi.getUsage

**Files:**
- Modify: `apps/web/src/lib/api/services.ts`

- [ ] **Step 1: Extend `panelsApi`**

Open `apps/web/src/lib/api/services.ts`. Locate `export const panelsApi = {` (around `:254`) and add a new method before the closing `}`:

```ts
    updateBindings: (
        panelId: string,
        payload: {
            slot: 'character' | 'scene' | 'prop'
            slot_index: number
            asset_id: string | null
            asset_version_id?: string | null
        }
    ) =>
        apiPatch<{
            panel_id: string
            spec_json: Record<string, unknown>
            chapter_bindings_updated: boolean
        }>(`/api/v1/panels/${panelId}/bindings`, payload),
```

- [ ] **Step 2: Extend `assetsApi`**

Locate `export const assetsApi = {` (around `:281`). Add before its closing `}`:

```ts
    getUsage: (id: string, limit = 50) =>
        apiGet<{
            asset_id: string
            references: Array<{
                chapter_id: string
                chapter_title: string | null
                panel_id: string
                panel_order: number
                panel_preview_url: string | null
            }>
            total_count: number
        }>(`/api/v1/assets/${id}/usage?limit=${limit}`),
```

- [ ] **Step 3: Typecheck**

Run: `cd apps/web && npx tsc --noEmit`
Expected: no errors (or at most pre-existing errors unrelated to these additions)

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/lib/api/services.ts
git commit -m "feat(web): add panelsApi.updateBindings + assetsApi.getUsage"
```

---

## Task 10: Wire AssetsTab "select asset" button

**Files:**
- Modify: `apps/web/src/components/studio/right/AssetsTab.tsx` (around `:629-636`)

- [ ] **Step 1: Replace the TODO onClick**

Find this block (near `:629`):

```tsx
                                    onClick={() => {
                                        // TODO: call bind API once backend endpoint is available
                                        console.log(`Bind ${bindingTarget?.id} → asset ${asset.id}`)
                                        setBindingTarget(null)
                                    }}
```

Replace with:

```tsx
                                    onClick={async () => {
                                        if (!bindingTarget) return
                                        try {
                                            await panelsApi.updateBindings(bindingTarget.panelId, {
                                                slot: bindingTarget.type === 'scene' ? 'scene' : 'character',
                                                slot_index: bindingTarget.slotIndex ?? 0,
                                                asset_id: asset.id,
                                            })
                                            toast({ title: '已绑定', description: `${asset.name} → ${bindingTarget.name}` })
                                            setBindingTarget(null)
                                            // Refresh panel in store
                                            if (bindingTarget.onBound) await bindingTarget.onBound()
                                        } catch (err) {
                                            toast({
                                                title: '绑定失败',
                                                description: err instanceof Error ? err.message : String(err),
                                                variant: 'destructive',
                                            })
                                        }
                                    }}
```

- [ ] **Step 2: Extend `bindingTarget` type**

Find the `useState<{ id: string; name: string; type: ... }>` declaration (around `:191`) and update it to:

```tsx
    const [bindingTarget, setBindingTarget] = useState<{
        id: string
        name: string
        type: 'character' | 'scene'
        panelId: string
        slotIndex?: number
        onBound?: () => Promise<void> | void
    } | null>(null)
```

Update the existing `setBindingTarget({ ... })` call around `:437` so it passes `panelId` and `slotIndex` from the caller. If the call site lacks that data, thread it through via props (the parent must already know `panelId` since it's the Studio Inspector context).

- [ ] **Step 3: Add imports at top of file**

Ensure these imports exist near the top of `AssetsTab.tsx`:

```tsx
import { panelsApi } from '@/lib/api/services'
import { toast } from '@/components/ui/toast'
```

(If the project uses `useToast()` hook instead of a direct `toast` import, follow that pattern — grep the file for existing toast usage first.)

- [ ] **Step 4: Manual smoke**

Start the dev server: `cd apps/web && npm run dev` → log in → navigate to a Studio page with panels → pick a panel → select a character asset in the binding dialog. Expect: toast "已绑定", dialog closes, panel card updates.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/studio/right/AssetsTab.tsx
git commit -m "feat(web): wire AssetsTab select to panel bindings API"
```

---

## Task 11: Wire AssetsTab "Create new asset" button

**Files:**
- Modify: `apps/web/src/components/studio/right/AssetsTab.tsx` (around `:701-707`)

- [ ] **Step 1: Replace the TODO**

Find:

```tsx
                        <Button
                            variant="secondary"
                            onClick={() => {
                                // TODO: wire up asset creation flow
                                console.log('Create new asset for:', bindingTarget?.name)
                                setBindingTarget(null)
                            }}
                        >
```

Replace the `onClick` handler with:

```tsx
                            onClick={() => {
                                if (!bindingTarget || !projectId) return
                                setCreateSeed({
                                    type: bindingTarget.type,
                                    name: bindingTarget.name,
                                    onCreated: async (newAsset) => {
                                        await panelsApi.updateBindings(bindingTarget.panelId, {
                                            slot: bindingTarget.type === 'scene' ? 'scene' : 'character',
                                            slot_index: bindingTarget.slotIndex ?? 0,
                                            asset_id: newAsset.id,
                                        })
                                        toast({ title: '新资产已创建并绑定', description: newAsset.name })
                                        setBindingTarget(null)
                                        setCreateSeed(null)
                                        if (bindingTarget.onBound) await bindingTarget.onBound()
                                    },
                                })
                            }}
```

- [ ] **Step 2: Add `createSeed` state + mount CreateAssetModal**

Near other `useState` calls (top of component, around `:191`), add:

```tsx
    const [createSeed, setCreateSeed] = useState<{
        type: 'character' | 'scene'
        name: string
        onCreated: (asset: { id: string; name: string }) => Promise<void>
    } | null>(null)
```

At the bottom of the JSX (before the closing `</div>` of the root), mount:

```tsx
            {createSeed && projectId && (
                <CreateAssetModal
                    open={true}
                    onOpenChange={(open) => { if (!open) setCreateSeed(null) }}
                    projects={[{ id: projectId, name: '' }] as any}
                    defaultProjectId={projectId}
                    defaultType={createSeed.type}
                    defaultName={createSeed.name}
                    onCreated={createSeed.onCreated}
                />
            )}
```

Import `CreateAssetModal` from its existing path (grep: `grep -rn "CreateAssetModal" apps/web/src | head -3`). If `CreateAssetModal` does not accept `defaultType/defaultName/onCreated` props, extend its interface in a separate step — for now pass what it accepts and post-create re-fetch the new asset from `assetsApi.list`.

- [ ] **Step 3: Manual smoke**

In browser: open binding dialog for an unbound character slot → click "创建新资产" → modal opens with name prefilled → create → toast appears, binding set.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/components/studio/right/AssetsTab.tsx
git commit -m "feat(web): wire 'Create new asset' to creation+autobind flow"
```

---

## Task 12: Add Clear binding button in AssetsTab dialog

**Files:**
- Modify: `apps/web/src/components/studio/right/AssetsTab.tsx` (the `DialogFooter` around `:697-712`)

- [ ] **Step 1: Add the button**

Locate the existing `DialogFooter` block. Add a third button between "取消" and "创建新资产" that is conditionally rendered when the current slot is already bound:

```tsx
                    <DialogFooter className="flex gap-2">
                        <Button variant="outline" onClick={() => setBindingTarget(null)}>
                            取消
                        </Button>
                        {bindingTarget?.currentAssetId && (
                            <Button
                                variant="ghost"
                                onClick={async () => {
                                    if (!bindingTarget) return
                                    try {
                                        await panelsApi.updateBindings(bindingTarget.panelId, {
                                            slot: bindingTarget.type === 'scene' ? 'scene' : 'character',
                                            slot_index: bindingTarget.slotIndex ?? 0,
                                            asset_id: null,
                                        })
                                        toast({ title: '已清除绑定' })
                                        setBindingTarget(null)
                                        if (bindingTarget.onBound) await bindingTarget.onBound()
                                    } catch (err) {
                                        toast({
                                            title: '清除失败',
                                            description: err instanceof Error ? err.message : String(err),
                                            variant: 'destructive',
                                        })
                                    }
                                }}
                            >
                                清除绑定
                            </Button>
                        )}
                        <Button variant="secondary" onClick={/* existing create handler */}>
                            <Wand2 className="w-4 h-4 mr-1" />
                            创建新资产
                        </Button>
                    </DialogFooter>
```

- [ ] **Step 2: Extend `bindingTarget` to carry `currentAssetId`**

Update the `useState` type added in Task 10 to include `currentAssetId?: string | null`. Update the caller that sets `bindingTarget` to pass the currently bound asset id (read from the panel's `spec_json.characters[slotIndex].asset_id`).

- [ ] **Step 3: Manual smoke**

Bind an asset → reopen the binding dialog for the same slot → "清除绑定" button visible → click → toast, slot cleared.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/components/studio/right/AssetsTab.tsx
git commit -m "feat(web): allow clearing a panel binding from dialog"
```

---

## Task 13: ScriptInput — add state machine

**Files:**
- Modify: `apps/web/src/components/script-editor/ScriptInput.tsx`

- [ ] **Step 1: Replace state and add `status`**

At the top of the component body (around `:42-46`), replace the individual state hooks with:

```tsx
    const [script, setScript] = useState('');
    const [style, setStyle] = useState('korean_webtoon');
    const [result, setResult] = useState<ScriptParseResult | null>(null);
    const [status, setStatus] = useState<
        'empty' | 'edited' | 'parsing' | 'preview' | 'generating' | 'done' | 'error'
    >('empty');
    const [error, setError] = useState<string | null>(null);
    const [storyboardJobId, setStoryboardJobId] = useState<string | null>(null);
    const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
```

Keep the `isParsing`/`showPreview` flags only if other code references them — else remove.

- [ ] **Step 2: Update `handleParse` to drive `status`**

Rewrite `handleParse` to:

```tsx
    const handleParse = useCallback(async () => {
        if (!script.trim()) {
            setError('请输入剧本内容');
            setStatus('error');
            return;
        }
        setStatus('parsing');
        setError(null);
        try {
            const response = await fetch(`${api.baseUrl}/api/v1/brain/parse-script`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ script_text: script, style_hint: style }),
            });
            if (!response.ok) throw new Error('解析失败');
            const data: ScriptParseResult = await response.json();
            setResult(data);
            setStatus('preview');
            onParsed?.(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : '解析失败');
            setStatus('error');
            onError?.(err instanceof Error ? err.message : '解析失败');
        }
    }, [script, style, onParsed, onError]);
```

- [ ] **Step 3: Drive `status` from `script` changes**

Replace the textarea's `onChange` at the bottom of the file:

```tsx
                    onChange={(e) => {
                        setScript(e.target.value);
                        if (status !== 'generating' && status !== 'parsing') {
                            setStatus(e.target.value.trim() ? 'edited' : 'empty');
                        }
                    }}
```

- [ ] **Step 4: Typecheck**

Run: `cd apps/web && npx tsc --noEmit -p .`
Expected: no new errors.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/script-editor/ScriptInput.tsx
git commit -m "feat(web): ScriptInput status state machine"
```

---

## Task 14: ScriptInput — wire handleConfirm to storyboard endpoint

**Files:**
- Modify: `apps/web/src/components/script-editor/ScriptInput.tsx` (the `handleConfirm` around `:80-85`)

- [ ] **Step 1: Implement handleConfirm**

Replace the existing `handleConfirm`:

```tsx
    const handleConfirm = useCallback(async () => {
        if (!chapterId) {
            setError('缺少章节 ID');
            setStatus('error');
            return;
        }
        setStatus('generating');
        setError(null);
        setProgress(null);
        try {
            const response = await fetch(
                `${api.baseUrl}/api/v1/chapters/${chapterId}/storyboard`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        provider: 'doubao',
                        style_hint: style,
                        target_panels: result?.panels?.length ?? null,
                        auto_apply: true,
                    }),
                },
            );
            if (!response.ok) throw new Error(`生成失败 (${response.status})`);
            const data: { job_id: string; status: string } = await response.json();
            setStoryboardJobId(data.job_id);
            if (data.status === 'succeeded') {
                setStatus('done');
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : '生成失败');
            setStatus('error');
        }
    }, [chapterId, style, result]);
```

- [ ] **Step 2: Replace the render of action buttons**

Below the textarea (insert or replace the existing action button area) add the state-driven button row:

```tsx
            <div className="px-4 py-3 border-t border-zinc-800 flex items-center gap-2">
                {status === 'empty' || status === 'edited' || status === 'error' ? (
                    <button
                        onClick={handleParse}
                        disabled={!script.trim()}
                        className="px-4 py-2 bg-emerald-600 text-white rounded disabled:opacity-50"
                    >
                        预览分镜
                    </button>
                ) : null}

                {status === 'parsing' ? (
                    <span className="text-sm text-zinc-400">解析中…</span>
                ) : null}

                {status === 'preview' ? (
                    <>
                        <button
                            onClick={handleConfirm}
                            className="px-4 py-2 bg-emerald-600 text-white rounded"
                        >
                            生成正式分镜
                        </button>
                        <button
                            onClick={handleParse}
                            className="px-4 py-2 bg-zinc-700 text-zinc-200 rounded"
                        >
                            重新预览
                        </button>
                    </>
                ) : null}

                {status === 'generating' ? (
                    <span className="text-sm text-zinc-400">
                        正在生成{progress ? `… ${progress.done}/${progress.total}` : '…'}
                    </span>
                ) : null}

                {status === 'done' ? (
                    <button
                        onClick={() => onParsed?.(result!)}
                        className="px-4 py-2 bg-emerald-600 text-white rounded"
                    >
                        查看分镜
                    </button>
                ) : null}

                {status === 'error' && error ? (
                    <span className="text-sm text-red-400">错误：{error}</span>
                ) : null}
            </div>
```

- [ ] **Step 3: Manual smoke (no WS yet)**

In browser: enter script → "预览分镜" → "生成正式分镜" → expect button switches to "正在生成…" then either "查看分镜" (if the backend call synchronously returned succeeded) or stays pending until Task 15 WS wiring lands.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/components/script-editor/ScriptInput.tsx
git commit -m "feat(web): wire ScriptInput confirm to /chapters/{id}/storyboard"
```

---

## Task 15: ScriptInput — subscribe to storyboard WS events

**Files:**
- Modify: `apps/web/src/components/script-editor/ScriptInput.tsx`

- [ ] **Step 1: Add WS subscription effect**

Import the WS client at the top of the file:

```tsx
import { wsClient } from '@/lib/ws/client';
```

(If the project exposes WS via a different hook or named export, grep `apps/web/src/lib/ws/client.ts` for the actual export first.)

Add an effect below the `useState` calls:

```tsx
    useEffect(() => {
        if (!storyboardJobId || !chapterId) return;
        const unsubProgress = wsClient.on('job_progress', (payload: any) => {
            if (payload.job_id !== storyboardJobId) return;
            const prog = typeof payload.progress === 'number' ? payload.progress : null;
            if (prog !== null) {
                const approxTotal = result?.panels?.length ?? 1;
                setProgress({
                    done: Math.round(prog * approxTotal),
                    total: approxTotal,
                });
            }
        });
        const unsubStatus = wsClient.on('job_status', (payload: any) => {
            if (payload.job_id !== storyboardJobId) return;
            if (payload.status === 'succeeded') setStatus('done');
            if (payload.status === 'failed') {
                setStatus('error');
                setError(payload.error || '生成失败');
            }
        });
        return () => {
            unsubProgress?.();
            unsubStatus?.();
        };
    }, [storyboardJobId, chapterId, result]);
```

Adjust `wsClient.on(...)` signature to match whatever the actual WS client exposes. If the current WS client uses a different event name or payload shape, consult `apps/web/src/lib/ws/events.ts` and adapt.

- [ ] **Step 2: Add `useEffect` to imports**

Ensure `useEffect` is imported alongside `useState`, `useCallback`.

- [ ] **Step 3: Manual smoke with real backend**

Start backend + Celery + frontend. Enter script → preview → confirm → watch the button text update live from WS events; on success button becomes "查看分镜".

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/components/script-editor/ScriptInput.tsx
git commit -m "feat(web): subscribe ScriptInput to storyboard WS progress"
```

---

## Task 16: AssetEditDrawer shell + Basic tab

**Files:**
- Create: `apps/web/src/components/assets/AssetEditDrawer.tsx`
- Create: `apps/web/src/components/assets/drawer/BasicTab.tsx`

- [ ] **Step 1: Write the shell**

```tsx
'use client'

import { useEffect, useState } from 'react'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { assetsApi } from '@/lib/api/services'
import type { Asset } from '@/lib/schema/asset'

import { BasicTab } from './drawer/BasicTab'

export interface AssetEditDrawerProps {
    assetId: string | null
    onClose: () => void
    onSaved?: (asset: Asset) => void
}

export function AssetEditDrawer({ assetId, onClose, onSaved }: AssetEditDrawerProps) {
    const [asset, setAsset] = useState<Asset | null>(null)
    const [draft, setDraft] = useState<Partial<Asset>>({})
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [tab, setTab] = useState<'basic' | 'traits' | 'versions' | 'usage'>('basic')

    useEffect(() => {
        if (!assetId) {
            setAsset(null)
            setDraft({})
            return
        }
        let alive = true
        assetsApi.get(assetId).then((a) => { if (alive) { setAsset(a); setDraft({}) } })
        return () => { alive = false }
    }, [assetId])

    const dirty = Object.keys(draft).length > 0

    const handleSave = async () => {
        if (!asset || !dirty) return
        setSaving(true)
        setError(null)
        try {
            const updated = await assetsApi.update(asset.id, draft)
            onSaved?.(updated)
            setAsset(updated)
            setDraft({})
        } catch (e) {
            setError(e instanceof Error ? e.message : String(e))
        } finally {
            setSaving(false)
        }
    }

    const handleClose = () => {
        if (dirty && !confirm('有未保存的改动，确定关闭？')) return
        onClose()
    }

    return (
        <Sheet open={!!assetId} onOpenChange={(o) => { if (!o) handleClose() }}>
            <SheetContent side="right" className="w-[560px] sm:max-w-[560px] flex flex-col p-0">
                <SheetHeader className="px-6 py-4 border-b border-white/10">
                    <div className="flex items-center gap-3">
                        {asset?.thumbnail_url ? (
                            <img src={asset.thumbnail_url} alt={asset.name}
                                className="w-10 h-10 rounded object-cover" />
                        ) : <div className="w-10 h-10 rounded bg-muted/40" />}
                        <div className="flex-1">
                            <SheetTitle className="truncate">{asset?.name ?? '…'}</SheetTitle>
                            {asset?.type && (
                                <Badge variant="outline" className="mt-1">{asset.type}</Badge>
                            )}
                        </div>
                    </div>
                </SheetHeader>

                <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)}
                    className="flex-1 flex flex-col overflow-hidden">
                    <TabsList className="mx-6 mt-4 justify-start">
                        <TabsTrigger value="basic">Basic</TabsTrigger>
                        <TabsTrigger value="traits">Traits</TabsTrigger>
                        <TabsTrigger value="versions">Versions</TabsTrigger>
                        <TabsTrigger value="usage">Usage</TabsTrigger>
                    </TabsList>
                    <div className="flex-1 overflow-y-auto px-6 py-4">
                        <TabsContent value="basic" className="mt-0">
                            {asset && <BasicTab asset={asset} draft={draft} onChange={setDraft} />}
                        </TabsContent>
                        <TabsContent value="traits" className="mt-0 text-sm text-muted-foreground">
                            Traits tab — see Task 17.
                        </TabsContent>
                        <TabsContent value="versions" className="mt-0 text-sm text-muted-foreground">
                            Versions tab — see Task 19.
                        </TabsContent>
                        <TabsContent value="usage" className="mt-0 text-sm text-muted-foreground">
                            Usage tab — see Task 18.
                        </TabsContent>
                    </div>
                </Tabs>

                <div className="border-t border-white/10 px-6 py-3 flex items-center justify-between">
                    <div className="text-xs text-muted-foreground">
                        {dirty ? `${Object.keys(draft).length} 项改动，未保存` : error ? (
                            <span className="text-red-400">{error}</span>
                        ) : '无改动'}
                    </div>
                    <div className="flex gap-2">
                        <Button variant="outline" onClick={handleClose} disabled={saving}>取消</Button>
                        <Button onClick={handleSave} disabled={!dirty || saving}>
                            {saving ? '保存中…' : '保存'}
                        </Button>
                    </div>
                </div>
            </SheetContent>
        </Sheet>
    )
}
```

Write to `apps/web/src/components/assets/AssetEditDrawer.tsx`.

- [ ] **Step 2: Write BasicTab**

```tsx
'use client'

import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { assetsApi } from '@/lib/api/services'
import type { Asset } from '@/lib/schema/asset'

export interface BasicTabProps {
    asset: Asset
    draft: Partial<Asset>
    onChange: (draft: Partial<Asset>) => void
}

export function BasicTab({ asset, draft, onChange }: BasicTabProps) {
    const current = { ...asset, ...draft } as Asset & Record<string, unknown>

    const update = (patch: Partial<Asset>) => onChange({ ...draft, ...patch })

    const handleRegenerate = async () => {
        await assetsApi.regenerateReference(asset.id)
    }

    return (
        <div className="space-y-4">
            <div>
                <Label>名称</Label>
                <Input
                    value={(current.name as string) ?? ''}
                    onChange={(e) => update({ name: e.target.value } as Partial<Asset>)}
                />
            </div>
            <div>
                <Label>描述</Label>
                <Textarea
                    rows={4}
                    value={(current.description as string) ?? ''}
                    onChange={(e) => update({ description: e.target.value } as Partial<Asset>)}
                />
            </div>
            <div>
                <Label>Tags（逗号分隔）</Label>
                <Input
                    value={Array.isArray(current.tags) ? current.tags.join(',') : ''}
                    onChange={(e) => update({
                        tags: e.target.value.split(',').map(t => t.trim()).filter(Boolean),
                    } as Partial<Asset>)}
                />
            </div>
            <div>
                <Label>封面</Label>
                <div className="mt-2 flex items-center gap-3">
                    {asset.thumbnail_url ? (
                        <img src={asset.thumbnail_url} alt="" className="w-24 h-24 object-cover rounded" />
                    ) : <div className="w-24 h-24 rounded bg-muted/30" />}
                    <Button variant="outline" onClick={handleRegenerate}>重新生成参考图</Button>
                </div>
            </div>
        </div>
    )
}
```

Write to `apps/web/src/components/assets/drawer/BasicTab.tsx`.

- [ ] **Step 3: Typecheck**

Run: `cd apps/web && npx tsc --noEmit`
Expected: no new errors. If `Asset` schema lacks `tags`/`description`, temporarily cast via `as any` — those fields already exist per memory notes.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/components/assets/AssetEditDrawer.tsx apps/web/src/components/assets/drawer/BasicTab.tsx
git commit -m "feat(web): scaffold AssetEditDrawer + BasicTab"
```

---

## Task 17: AssetEditDrawer — TraitsTab

**Files:**
- Create: `apps/web/src/components/assets/drawer/TraitsTab.tsx`
- Modify: `apps/web/src/components/assets/AssetEditDrawer.tsx`

- [ ] **Step 1: Write TraitsTab**

```tsx
'use client'

import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import type { Asset } from '@/lib/schema/asset'

export interface TraitsTabProps {
    asset: Asset
    draft: Partial<Asset>
    onChange: (draft: Partial<Asset>) => void
}

export function TraitsTab({ asset, draft, onChange }: TraitsTabProps) {
    const dataJson: Record<string, unknown> = {
        ...((asset as any).data_json ?? {}),
        ...((draft as any).data_json ?? {}),
    }
    const update = (patch: Record<string, unknown>) => {
        onChange({ ...draft, data_json: { ...dataJson, ...patch } } as Partial<Asset>)
    }

    if (asset.type === 'character') {
        return (
            <div className="space-y-4">
                <div>
                    <Label>外貌特征（逗号分隔）</Label>
                    <Input
                        value={(dataJson.appearance_traits as string[] | undefined)?.join(',') ?? ''}
                        onChange={(e) => update({
                            appearance_traits: e.target.value.split(',').map(s => s.trim()).filter(Boolean),
                        })}
                    />
                </div>
                <div>
                    <Label>服饰备注</Label>
                    <Textarea
                        rows={2}
                        value={(dataJson.wardrobe_notes as string) ?? ''}
                        onChange={(e) => update({ wardrobe_notes: e.target.value })}
                    />
                </div>
                <div>
                    <Label>性格特征（逗号分隔）</Label>
                    <Input
                        value={(dataJson.personality_traits as string[] | undefined)?.join(',') ?? ''}
                        onChange={(e) => update({
                            personality_traits: e.target.value.split(',').map(s => s.trim()).filter(Boolean),
                        })}
                    />
                </div>
            </div>
        )
    }

    if (asset.type === 'scene') {
        return (
            <div className="space-y-4">
                <div>
                    <Label>时间</Label>
                    <Input
                        value={(dataJson.time_of_day as string) ?? ''}
                        onChange={(e) => update({ time_of_day: e.target.value })}
                    />
                </div>
                <div>
                    <Label>天气</Label>
                    <Input
                        value={(dataJson.weather as string) ?? ''}
                        onChange={(e) => update({ weather: e.target.value })}
                    />
                </div>
                <div>
                    <Label>氛围</Label>
                    <Input
                        value={(dataJson.mood as string) ?? ''}
                        onChange={(e) => update({ mood: e.target.value })}
                    />
                </div>
            </div>
        )
    }

    return (
        <p className="text-sm text-muted-foreground">
            此类型资产暂无 Traits 字段。
        </p>
    )
}
```

Write to `apps/web/src/components/assets/drawer/TraitsTab.tsx`.

- [ ] **Step 2: Wire into Drawer**

In `AssetEditDrawer.tsx`, replace the placeholder `TabsContent value="traits"` block with:

```tsx
                        <TabsContent value="traits" className="mt-0">
                            {asset && <TraitsTab asset={asset} draft={draft} onChange={setDraft} />}
                        </TabsContent>
```

And add the import at the top:

```tsx
import { TraitsTab } from './drawer/TraitsTab'
```

- [ ] **Step 3: Typecheck + commit**

```bash
cd apps/web && npx tsc --noEmit
git add apps/web/src/components/assets/
git commit -m "feat(web): AssetEditDrawer TraitsTab (character/scene)"
```

---

## Task 18: AssetEditDrawer — UsageTab

**Files:**
- Create: `apps/web/src/components/assets/drawer/UsageTab.tsx`
- Modify: `apps/web/src/components/assets/AssetEditDrawer.tsx`

- [ ] **Step 1: Write UsageTab**

```tsx
'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { assetsApi } from '@/lib/api/services'
import { Loader2 } from 'lucide-react'

export interface UsageTabProps {
    assetId: string
}

type Usage = Awaited<ReturnType<typeof assetsApi.getUsage>>

export function UsageTab({ assetId }: UsageTabProps) {
    const [data, setData] = useState<Usage | null>(null)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        let alive = true
        setData(null)
        setError(null)
        assetsApi.getUsage(assetId)
            .then((d) => { if (alive) setData(d) })
            .catch((e) => { if (alive) setError(e instanceof Error ? e.message : String(e)) })
        return () => { alive = false }
    }, [assetId])

    if (error) return <p className="text-sm text-red-400">加载失败：{error}</p>
    if (!data) return <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="w-4 h-4 animate-spin" /> 加载引用…
    </div>
    if (data.total_count === 0) return <p className="text-sm text-muted-foreground">此资产尚未被任何分镜引用。</p>

    return (
        <div className="space-y-2">
            <p className="text-xs text-muted-foreground">共 {data.total_count} 处引用</p>
            {data.references.map((ref) => (
                <Link
                    key={ref.panel_id}
                    href={`/projects/_/chapters/${ref.chapter_id}/studio?panel=${ref.panel_id}`}
                    className="flex items-center gap-3 p-2 rounded hover:bg-white/5"
                >
                    {ref.panel_preview_url ? (
                        <img src={ref.panel_preview_url} alt="" className="w-12 h-12 rounded object-cover" />
                    ) : <div className="w-12 h-12 rounded bg-muted/30" />}
                    <div className="flex-1 min-w-0">
                        <p className="truncate text-sm">{ref.chapter_title ?? ref.chapter_id}</p>
                        <p className="text-xs text-muted-foreground">Panel #{ref.panel_order}</p>
                    </div>
                </Link>
            ))}
        </div>
    )
}
```

Write to `apps/web/src/components/assets/drawer/UsageTab.tsx`.

Note: the `href="/projects/_/chapters/.../studio"` uses a placeholder project id because the usage API does not return project id directly. If the Studio route requires the real project id in the path, fetch it via `assetsApi.get(assetId)` (which carries `project_id`) and substitute — update this component in a follow-up.

- [ ] **Step 2: Wire into Drawer**

In `AssetEditDrawer.tsx`:

```tsx
import { UsageTab } from './drawer/UsageTab'
```

Replace the placeholder `TabsContent value="usage"`:

```tsx
                        <TabsContent value="usage" className="mt-0">
                            {asset && <UsageTab assetId={asset.id} />}
                        </TabsContent>
```

- [ ] **Step 3: Typecheck + commit**

```bash
cd apps/web && npx tsc --noEmit
git add apps/web/src/components/assets/
git commit -m "feat(web): AssetEditDrawer UsageTab (consumes /assets/{id}/usage)"
```

---

## Task 19: AssetEditDrawer — VersionsTab (empty state)

**Files:**
- Create: `apps/web/src/components/assets/drawer/VersionsTab.tsx`
- Modify: `apps/web/src/components/assets/AssetEditDrawer.tsx`

- [ ] **Step 1: Write empty-state VersionsTab**

```tsx
'use client'

export interface VersionsTabProps {
    assetId: string
}

export function VersionsTab({ assetId: _assetId }: VersionsTabProps) {
    return (
        <div className="py-8 text-center text-sm text-muted-foreground">
            <p>版本历史功能即将上线。</p>
            <p className="mt-1 text-xs">当前资产的所有渲染/修改会在此显示时间线。</p>
        </div>
    )
}
```

Write to `apps/web/src/components/assets/drawer/VersionsTab.tsx`.

- [ ] **Step 2: Wire into Drawer**

In `AssetEditDrawer.tsx`:

```tsx
import { VersionsTab } from './drawer/VersionsTab'
```

Replace placeholder:

```tsx
                        <TabsContent value="versions" className="mt-0">
                            {asset && <VersionsTab assetId={asset.id} />}
                        </TabsContent>
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/assets/
git commit -m "feat(web): AssetEditDrawer VersionsTab empty state"
```

---

## Task 20: Wire /assets edit button to AssetEditDrawer

**Files:**
- Modify: `apps/web/src/app/assets/page.tsx` (around `:534`)

- [ ] **Step 1: Add state + mount the Drawer**

Near the top of the component body (next to other `useState` calls), add:

```tsx
    const [editingAssetId, setEditingAssetId] = useState<string | null>(null)
```

Import:

```tsx
import { AssetEditDrawer } from '@/components/assets/AssetEditDrawer'
```

Just before the existing `<CreateAssetModal ... />` at the bottom of the JSX, add:

```tsx
            <AssetEditDrawer
                assetId={editingAssetId}
                onClose={() => setEditingAssetId(null)}
                onSaved={() => { loadData() }}
            />
```

- [ ] **Step 2: Replace the TODO**

Find `:534`:

```tsx
                                onEdit={() => {/* TODO: Implement edit modal */ }}
```

Replace with:

```tsx
                                onEdit={() => setEditingAssetId(asset.id)}
```

- [ ] **Step 3: Manual smoke**

`cd apps/web && npm run dev` → open `/assets` → click edit on a character card → Drawer slides in → change name → save → Drawer closes → list refreshes with new name. Also try switching to Usage tab.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/app/assets/page.tsx
git commit -m "feat(web): wire /assets edit button to AssetEditDrawer"
```

---

## Task 21: End-to-end verification + acceptance checklist

**Files:** none

- [ ] **Step 1: Run all backend tests**

Run: `cd apps/api && pytest tests/unit/services/test_binding_service.py tests/unit/routes/test_panel_bindings.py tests/unit/routes/test_asset_usage.py -v`
Expected: all pass.

- [ ] **Step 2: Run frontend lint**

Run: `cd apps/web && npm run lint`
Expected: no new warnings/errors.

- [ ] **Step 3: Walk the spec's Journey 1 → 4 manually**

Launch: postgres/redis/minio via `cd docker && docker compose up -d`; backend `uvicorn app.main:app --reload`; celery worker; `npm run dev`. Then:

- [ ] Journey 1: new chapter → ScriptInput → 预览 → 生成正式分镜 → 画布出现分镜
- [ ] Journey 2: pick a panel → AssetsTab → bind a character → reload page → binding persists
- [ ] Journey 3: `/assets` → edit a character → save → change visible in Studio
- [ ] Journey 4: reopen binding dialog → click 清除绑定 → slot empty

- [ ] **Step 4: Tick spec §10 acceptance**

Open `docs/superpowers/specs/2026-04-20-cluster-a-main-loop-design.md` §10. Confirm each checkbox.

- [ ] **Step 5: Final commit**

If any small fixes were made during verification, commit them. Otherwise:

```bash
git log --oneline -n 25
```

Expected: clean series of feat/test commits for Cluster A.

---

## Out of scope (do NOT add to this plan)

- LLM auto-binding confidence badges / dashed borders
- `AssetVersion` editing, diff, or "set active" API
- Popover-based binding UX (keep Dialog)
- Removal of `/brain/parse-script` or legacy `_chapters_legacy.py`
- FaceID binding UI inside the Drawer (lives in Cluster C)
- Canvas layer visualization
- Drag-and-drop asset binding
