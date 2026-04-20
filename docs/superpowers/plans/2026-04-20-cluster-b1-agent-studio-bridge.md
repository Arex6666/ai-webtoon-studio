# Cluster B1 — Agent ↔ Studio Bridge Implementation Plan (v2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bridge Agent and Studio modes — Agent conversation outputs can be committed to DB as real `Chapter + Panel + Asset`, editable in Studio. Supports both **single-episode commit from episode detail page** (full payload) and **bulk commit from list page** (lean payload; backend reads conversation to fill in).

**Architecture:**
- Backend: pure-function spec/asset builders + transactional orchestrator. A new `conversation_reader` service reads `ConversationMessage.entities_json` to reconstruct agent payload server-side when the request is lean. No DDL — `chapter.layout_json.source` as idempotency key, `asset.data_json.created_via` for provenance.
- Frontend: `/chat` becomes landing + project picker; `/chat/[projectId]` is the real chat page. Episode **detail** page has single-click "Open in Studio" (full data from page state); episode **list** page has "Bulk commit all" (lean payload, server reconstruction). Studio topbar shows Back-to-Agent link. Asset badges mark Agent origin.
- Idempotency: `(conversation_id, episode_number)` scanned from existing chapters; second commit returns `already_exists`.
- Image strategy: synchronous download temp URLs → MinIO at commit time; per-image failures non-fatal (warnings array).

**Tech Stack:** FastAPI + SQLAlchemy + Pydantic v2 (backend); Next.js 14 + Zustand + shadcn/ui + Radix DropdownMenu (frontend); pytest w/ mocked HTTP; manual smoke for frontend.

**Spec:** `docs/superpowers/specs/2026-04-20-cluster-b1-agent-studio-bridge-design.md`

---

## File Structure

### Backend
```
apps/api/app/
├── schemas/agent_commit.py                      CREATE  — request/response models
├── services/agent_commit/                       CREATE  — new package
│   ├── __init__.py                              CREATE
│   ├── image_fetcher.py                         CREATE  — HTTP→MinIO
│   ├── spec_builder.py                          CREATE  — pure: agent panel → PanelSpec
│   ├── asset_sync.py                            CREATE  — upsert Asset w/ image
│   ├── idempotency.py                           CREATE  — existing chapter lookup
│   ├── conversation_reader.py                   CREATE  — read Agent data from conversation
│   └── commit_orchestrator.py                   CREATE  — transactional orchestrator
└── api/routes/agent.py                          MODIFY  — add POST /projects/{pid}/commit-to-studio

apps/api/tests/unit/services/
├── test_agent_spec_builder.py                   CREATE
├── test_agent_asset_sync.py                     CREATE
├── test_agent_idempotency.py                    CREATE
└── test_agent_conversation_reader.py            CREATE

apps/api/tests/unit/routes/
└── test_agent_commit.py                         CREATE
```

### Frontend
```
apps/web/src/
├── lib/api/services.ts                           MODIFY  — add agentApi.commitToStudio
├── app/chat/
│   ├── page.tsx                                  MODIFY  — landing
│   └── [projectId]/page.tsx                      CREATE  — conversation page
├── components/chat/
│   ├── ChatProjectPicker.tsx                     CREATE
│   └── ChatEmptyState.tsx                        CREATE
├── app/agent/[projectId]/episodes/
│   ├── page.tsx                                  MODIFY  — bulk commit button (lean)
│   └── [episodeNum]/page.tsx                     MODIFY  — single Open-in-Studio (full)
├── components/studio/StudioTopbar.tsx            MODIFY  — back-to-Agent link
└── components/assets/
    ├── AssetSourceBadge.tsx                      CREATE
    ├── drawer/BasicTab.tsx                       MODIFY
    └── (via AssetsTab + /assets page)            MODIFY
```

---

## Task 1: Pydantic schemas

**Files:** Create `apps/api/app/schemas/agent_commit.py`

- [ ] **Step 1: Write the file**

```python
"""Agent → Studio commit schemas."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class AgentArtStyle(BaseModel):
    base_style: str = ""
    color_tone: str = ""
    atmosphere: str = ""


class AgentCharacter(BaseModel):
    name: str
    visual_prompt: Optional[str] = None
    temp_image_url: Optional[str] = None
    appearance_traits: List[str] = Field(default_factory=list)
    personality_traits: List[str] = Field(default_factory=list)
    wardrobe_notes: Optional[str] = None


class AgentScene(BaseModel):
    name: str
    visual_prompt: Optional[str] = None
    temp_image_url: Optional[str] = None
    time_of_day: Optional[str] = None
    weather: Optional[str] = None
    mood: Optional[str] = None


class AgentPanel(BaseModel):
    id: str
    order: int = 0
    scene_name: Optional[str] = None
    characters: List[str] = Field(default_factory=list)
    scene_description: str = ""
    dialogue: Optional[str] = None
    shot_type: str = "MS"
    camera_angle: str = "eye-level"
    emotion: Optional[str] = None
    composition: Optional[str] = None
    temp_image_url: Optional[str] = None


class CommitToStudioRequest(BaseModel):
    """Full payload if frontend has the data; or lean if only conversation+episode given.

    If `panels` is empty, backend will try to reconstruct from the conversation.
    """
    conversation_id: str
    episode_number: int = Field(..., ge=1)
    episode_title: str = ""
    outline_summary: str = ""
    art_style: AgentArtStyle = Field(default_factory=AgentArtStyle)
    characters: List[AgentCharacter] = Field(default_factory=list)
    scenes: List[AgentScene] = Field(default_factory=list)
    panels: List[AgentPanel] = Field(default_factory=list)


class CommitCreatedCounts(BaseModel):
    characters: int = 0
    scenes: int = 0


class CommitToStudioResponse(BaseModel):
    chapter_id: str
    chapter_title: str
    status: str  # "created" | "already_exists"
    created_assets: CommitCreatedCounts
    created_panels: int
    studio_url: str
    warnings: List[str] = Field(default_factory=list)
    payload_source: str = "request"  # "request" | "conversation"
```

- [ ] **Step 2: Verify import**

`cd apps/api && python -c "from app.schemas.agent_commit import CommitToStudioRequest, CommitToStudioResponse; print('ok')"` → `ok`

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/schemas/agent_commit.py
git commit -m "feat(api): agent commit-to-studio pydantic schemas"
```

---

## Task 2: Image fetcher helper

**Files:** Create `apps/api/app/services/agent_commit/__init__.py` (stub) + `image_fetcher.py`

- [ ] **Step 1: `__init__.py` (minimal now; will be updated in Task 9)**

```python
"""Agent commit-to-studio service."""
```

- [ ] **Step 2: Write `image_fetcher.py`**

```python
"""Download a remote image and store it in MinIO, returning the storage key."""
from __future__ import annotations

import logging
import mimetypes
import uuid
from typing import Optional

import httpx

from app.core.storage import storage_client

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 20 * 1024 * 1024
DEFAULT_TIMEOUT_S = 15.0


class ImageFetchError(Exception):
    pass


async def fetch_and_persist(
    url: str,
    *,
    project_id: str,
    asset_type: str,
    name_hint: str,
) -> str:
    """Download `url`, upload to MinIO under a deterministic key, return the key.

    Raises ImageFetchError on any failure.
    """
    if not url:
        raise ImageFetchError("empty url")

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_S, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.content
            if len(data) > MAX_IMAGE_BYTES:
                raise ImageFetchError(f"image exceeds {MAX_IMAGE_BYTES} bytes")
            content_type = resp.headers.get("content-type", "image/png").split(";")[0].strip()
    except ImageFetchError:
        raise
    except Exception as e:
        raise ImageFetchError(f"download failed: {e}") from e

    ext = mimetypes.guess_extension(content_type) or ".png"
    safe_hint = "".join(c if c.isalnum() else "_" for c in name_hint)[:40]
    key = f"agent-commit/{project_id}/{asset_type}/{safe_hint}-{uuid.uuid4().hex[:8]}{ext}"

    try:
        storage_client.put_bytes(key, data, content_type=content_type)
    except Exception as e:
        raise ImageFetchError(f"minio upload failed: {e}") from e

    return key
```

- [ ] **Step 3: Verify; inspect storage_client if needed**

`cd apps/api && python -c "from app.services.agent_commit.image_fetcher import fetch_and_persist, ImageFetchError; print('ok')"`

If `storage_client.put_bytes` isn't the right method name, grep `apps/api/app/core/storage.py` for the actual upload method (candidates: `put_object`, `upload_bytes`). Replace in the file.

- [ ] **Step 4: Commit**

```bash
git add apps/api/app/services/agent_commit/
git commit -m "feat(api): agent_commit image_fetcher helper"
```

---

## Task 3: Spec builder (pure)

**Files:** Create `apps/api/app/services/agent_commit/spec_builder.py`

- [ ] **Step 1: Write the file**

```python
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
```

- [ ] **Step 2: Verify**

`cd apps/api && python -c "from app.services.agent_commit.spec_builder import build_panel_spec, build_chapter_source; print('ok')"`

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/services/agent_commit/spec_builder.py
git commit -m "feat(api): agent_commit pure spec_builder"
```

---

## Task 4: spec_builder unit tests

**Files:** Create `apps/api/tests/unit/services/test_agent_spec_builder.py`

- [ ] **Step 1: Write tests**

```python
"""Unit tests for agent_commit.spec_builder (pure functions)."""
from app.schemas.agent_commit import AgentPanel, AgentArtStyle
from app.services.agent_commit.spec_builder import build_panel_spec, build_chapter_source


def make_panel(**kw):
    defaults = dict(
        id="agent-panel-1", order=0, scene_name="rooftop",
        characters=["Alice", "Bob"], scene_description="they meet",
        shot_type="MS", camera_angle="eye-level",
    )
    defaults.update(kw)
    return AgentPanel(**defaults)


class TestBuildPanelSpec:
    def test_maps_core_fields(self):
        spec = build_panel_spec(
            make_panel(),
            panel_id="p-uuid",
            character_name_to_id={"Alice": "a-id", "Bob": "b-id"},
            scene_name_to_id={"rooftop": "scene-id"},
            art_style=AgentArtStyle(base_style="Korean webtoon"),
        )
        assert spec["id"] == "p-uuid"
        assert spec["index"] == 0
        assert spec["shot"]["shotType"] == "MS"
        assert spec["scene"]["anchor_id"] == "scene-id"
        assert spec["characters"][0] == {"name": "Alice", "asset_id": "a-id"}
        assert spec["characters"][1] == {"name": "Bob", "asset_id": "b-id"}
        assert spec["meta"]["source"] == "agent"
        assert spec["meta"]["agent_panel_id"] == "agent-panel-1"

    def test_unknown_character_no_asset_id(self):
        spec = build_panel_spec(
            make_panel(characters=["Unknown"]),
            panel_id="p-uuid", character_name_to_id={}, scene_name_to_id={},
            art_style=AgentArtStyle(),
        )
        assert spec["characters"][0] == {"name": "Unknown"}

    def test_scene_without_anchor(self):
        spec = build_panel_spec(
            make_panel(scene_name="nowhere"),
            panel_id="p-uuid", character_name_to_id={}, scene_name_to_id={},
            art_style=AgentArtStyle(),
        )
        assert "anchor_id" not in spec["scene"]

    def test_dialogue_empty_list_when_no_dialogue(self):
        spec = build_panel_spec(
            make_panel(),
            panel_id="p-uuid", character_name_to_id={}, scene_name_to_id={},
            art_style=AgentArtStyle(),
        )
        assert spec["dialogue"]["lines"] == []

    def test_dialogue_line_when_present(self):
        spec = build_panel_spec(
            make_panel(dialogue="hi"),
            panel_id="p-uuid", character_name_to_id={}, scene_name_to_id={},
            art_style=AgentArtStyle(),
        )
        assert spec["dialogue"]["lines"] == [{"speaker": "Unknown", "text": "hi", "type": "speech"}]


class TestBuildChapterSource:
    def test_contains_required_keys(self):
        src = build_chapter_source(
            conversation_id="conv-1", episode_number=3,
            art_style=AgentArtStyle(base_style="X"),
        )
        assert src["type"] == "agent"
        assert src["conversation_id"] == "conv-1"
        assert src["episode_number"] == 3
        assert "committed_at" in src
        assert src["art_style_snapshot"]["base_style"] == "X"
```

- [ ] **Step 2: Run** `cd apps/api && pytest tests/unit/services/test_agent_spec_builder.py -v` → 6 pass

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/unit/services/test_agent_spec_builder.py
git commit -m "test(api): cover agent_commit.spec_builder"
```

---

## Task 5: Asset sync service

**Files:** Create `apps/api/app/services/agent_commit/asset_sync.py`

- [ ] **Step 1: Write the file**

```python
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
```

- [ ] **Step 2: Verify import**

`cd apps/api && python -c "from app.services.agent_commit.asset_sync import sync_character, sync_scene; print('ok')"`

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/services/agent_commit/asset_sync.py
git commit -m "feat(api): agent_commit asset_sync"
```

---

## Task 6: asset_sync tests

**Files:** Create `apps/api/tests/unit/services/test_agent_asset_sync.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for agent_commit.asset_sync — DB-backed, mocks image fetcher."""
import uuid
import pytest
from unittest.mock import AsyncMock, patch

from app.schemas.agent_commit import AgentCharacter, AgentScene


@pytest.fixture
def project_in_db(test_client):
    import os; os.environ["ENABLE_AUTH"] = "false"
    from app.core.database import SessionLocal
    from app.models.project import Project
    db = SessionLocal()
    try:
        proj = Project(id=str(uuid.uuid4()), name="AST", description="")
        db.add(proj); db.commit()
        return proj.id
    finally:
        db.close()


class TestSyncCharacter:
    @pytest.mark.asyncio
    async def test_creates_new_character(self, project_in_db):
        from app.core.database import SessionLocal
        from app.services.agent_commit.asset_sync import sync_character
        from app.models.asset import Asset

        db = SessionLocal()
        try:
            with patch("app.services.agent_commit.asset_sync.fetch_and_persist",
                       new=AsyncMock(return_value="key/x.png")):
                char = AgentCharacter(name="Alice", temp_image_url="http://x.png")
                asset_id, warnings = await sync_character(db, project_in_db, char, source_conversation_id="conv-1")
                db.commit()
            assert warnings == []
            asset = db.query(Asset).filter(Asset.id == asset_id).first()
            assert asset is not None and asset.name == "Alice" and asset.type == "character"
            assert asset.thumbnail_url == "key/x.png"
            assert asset.data_json["created_via"] == "agent"
            assert asset.data_json["source_conversation_id"] == "conv-1"
        finally:
            db.close()

    @pytest.mark.asyncio
    async def test_reuses_existing_character(self, project_in_db):
        from app.core.database import SessionLocal
        from app.services.agent_commit.asset_sync import sync_character
        from app.models.asset import Asset

        db = SessionLocal()
        existing = Asset(id=str(uuid.uuid4()), project_id=project_in_db, type="character",
                         name="Bob", data_json={"created_via": "studio"})
        db.add(existing); db.commit(); existing_id = existing.id; db.close()

        db2 = SessionLocal()
        try:
            char = AgentCharacter(name="Bob")
            asset_id, warnings = await sync_character(db2, project_in_db, char, source_conversation_id="conv-2")
            assert asset_id == existing_id
            assert warnings == []
            asset = db2.query(Asset).filter(Asset.id == existing_id).first()
            assert asset.data_json["created_via"] == "studio"
        finally:
            db2.close()

    @pytest.mark.asyncio
    async def test_image_fetch_failure_becomes_warning(self, project_in_db):
        from app.core.database import SessionLocal
        from app.services.agent_commit.asset_sync import sync_character
        from app.services.agent_commit.image_fetcher import ImageFetchError
        from app.models.asset import Asset

        db = SessionLocal()
        try:
            with patch("app.services.agent_commit.asset_sync.fetch_and_persist",
                       new=AsyncMock(side_effect=ImageFetchError("404"))):
                char = AgentCharacter(name="Eve", temp_image_url="http://dead.png")
                asset_id, warnings = await sync_character(db, project_in_db, char, source_conversation_id="c")
                db.commit()
            assert len(warnings) == 1 and "Eve" in warnings[0]
            asset = db.query(Asset).filter(Asset.id == asset_id).first()
            assert asset.thumbnail_url is None
        finally:
            db.close()


class TestSyncScene:
    @pytest.mark.asyncio
    async def test_creates_new_scene(self, project_in_db):
        from app.core.database import SessionLocal
        from app.services.agent_commit.asset_sync import sync_scene
        from app.models.asset import Asset

        db = SessionLocal()
        try:
            with patch("app.services.agent_commit.asset_sync.fetch_and_persist",
                       new=AsyncMock(return_value="key/s.png")):
                scene = AgentScene(name="Rooftop", temp_image_url="http://s.png", time_of_day="sunset")
                asset_id, warnings = await sync_scene(db, project_in_db, scene, source_conversation_id="c-1")
                db.commit()
            asset = db.query(Asset).filter(Asset.id == asset_id).first()
            assert asset is not None and asset.type == "scene"
            assert asset.data_json["time_of_day"] == "sunset"
        finally:
            db.close()
```

- [ ] **Step 2: Run** `cd apps/api && pytest tests/unit/services/test_agent_asset_sync.py -v` → 4 pass

If `pytest-asyncio` is missing, `pip install pytest-asyncio`.

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/unit/services/test_agent_asset_sync.py
git commit -m "test(api): cover agent_commit.asset_sync"
```

---

## Task 7: Idempotency lookup + tests

**Files:** Create `apps/api/app/services/agent_commit/idempotency.py` + `tests/unit/services/test_agent_idempotency.py`

- [ ] **Step 1: Write the service**

```python
"""Look up a chapter previously committed for the same (conversation, episode)."""
from __future__ import annotations
from typing import Optional
from sqlalchemy.orm import Session

from app.models.chapter import Chapter


def find_existing_chapter(
    db: Session, *, project_id: str, conversation_id: str, episode_number: int,
) -> Optional[Chapter]:
    """Scan chapters for matching layout_json.source. O(n) but n is small."""
    chapters = db.query(Chapter).filter(Chapter.project_id == project_id).all()
    for ch in chapters:
        source = (ch.layout_json or {}).get("source")
        if not source:
            continue
        if (source.get("type") == "agent"
                and source.get("conversation_id") == conversation_id
                and source.get("episode_number") == episode_number):
            return ch
    return None
```

- [ ] **Step 2: Write tests**

```python
"""Tests for agent_commit.idempotency."""
import uuid
import pytest


@pytest.fixture
def seeded(test_client):
    import os; os.environ["ENABLE_AUTH"] = "false"
    from app.core.database import SessionLocal
    from app.models.project import Project
    from app.models.chapter import Chapter

    db = SessionLocal()
    try:
        proj = Project(id=str(uuid.uuid4()), name="I", description="")
        db.add(proj)
        ch1 = Chapter(id=str(uuid.uuid4()), project_id=proj.id, title="ep1",
                      layout_json={"source": {"type": "agent", "conversation_id": "c1", "episode_number": 1}})
        ch2 = Chapter(id=str(uuid.uuid4()), project_id=proj.id, title="ep2",
                      layout_json={"source": {"type": "agent", "conversation_id": "c1", "episode_number": 2}})
        ch_plain = Chapter(id=str(uuid.uuid4()), project_id=proj.id, title="manual",
                           layout_json={})
        db.add_all([ch1, ch2, ch_plain]); db.commit()
        return {"project_id": proj.id, "ch1_id": ch1.id, "ch2_id": ch2.id}
    finally:
        db.close()


def test_finds_matching_chapter(seeded):
    from app.core.database import SessionLocal
    from app.services.agent_commit.idempotency import find_existing_chapter
    db = SessionLocal()
    try:
        ch = find_existing_chapter(db, project_id=seeded["project_id"], conversation_id="c1", episode_number=1)
        assert ch is not None and ch.id == seeded["ch1_id"]
    finally:
        db.close()


def test_returns_none_for_unknown_episode(seeded):
    from app.core.database import SessionLocal
    from app.services.agent_commit.idempotency import find_existing_chapter
    db = SessionLocal()
    try:
        ch = find_existing_chapter(db, project_id=seeded["project_id"], conversation_id="c1", episode_number=99)
        assert ch is None
    finally:
        db.close()


def test_returns_none_for_different_conversation(seeded):
    from app.core.database import SessionLocal
    from app.services.agent_commit.idempotency import find_existing_chapter
    db = SessionLocal()
    try:
        ch = find_existing_chapter(db, project_id=seeded["project_id"], conversation_id="c-other", episode_number=1)
        assert ch is None
    finally:
        db.close()


def test_ignores_chapter_without_source(seeded):
    from app.core.database import SessionLocal
    from app.services.agent_commit.idempotency import find_existing_chapter
    db = SessionLocal()
    try:
        ch = find_existing_chapter(db, project_id=seeded["project_id"], conversation_id="c1", episode_number=1)
        assert ch.id == seeded["ch1_id"]
    finally:
        db.close()
```

- [ ] **Step 3: Run** `cd apps/api && pytest tests/unit/services/test_agent_idempotency.py -v` → 4 pass

- [ ] **Step 4: Commit**

```bash
git add apps/api/app/services/agent_commit/idempotency.py \
        apps/api/tests/unit/services/test_agent_idempotency.py
git commit -m "feat(api): agent_commit idempotency + tests"
```

---

## Task 8: Conversation reader (lean-payload fallback) + tests

**Files:** Create `apps/api/app/services/agent_commit/conversation_reader.py` + `tests/unit/services/test_agent_conversation_reader.py`

- [ ] **Step 1: Investigate the Conversation / ConversationMessage model first**

Read `apps/api/app/models/conversation.py` and `apps/api/app/models/conversation_message.py` to understand:
- What fields exist on `ConversationMessage` (likely: `id`, `conversation_id`, `role`, `content`, `entities_json`)
- How agent data is stored in `entities_json` — especially:
  - Outline cards: `entities_json.card = { type: "outline", episodes: [...] }` (per the episodes page at `apps/web/src/app/agent/[projectId]/episodes/page.tsx:58`)
  - Panel cards: likely `entities_json.card = { type: "panels", episode_number, panels: [...] }` or similar
  - Character/scene cards: explore the structure

Also briefly grep `entities_json` across both `apps/api` and `apps/web` to confirm the shape conventions.

- [ ] **Step 2: Write the reader service**

```python
"""Reconstruct AgentCommit payload from ConversationMessage.entities_json cards.

If the frontend sends a lean payload ({conversation_id, episode_number, [title, summary]}),
this service scans messages in that conversation and extracts agent data for the target episode.
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
    needs_style = (req.art_style.base_style == "" and req.art_style.color_tone == ""
                   and req.art_style.atmosphere == "")

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

        if needs_panels and ctype == "panels" and card.get("episode_number") == req.episode_number:
            raw_panels = card.get("panels", []) or []
            for i, p in enumerate(raw_panels):
                if not isinstance(p, dict):
                    continue
                try:
                    panels.append(AgentPanel(
                        id=str(p.get("id") or f"conv-panel-{i}"),
                        order=int(p.get("order") if p.get("order") is not None else i),
                        scene_name=p.get("scene_name") or p.get("scene"),
                        characters=list(p.get("characters") or []),
                        scene_description=p.get("scene_description") or p.get("description") or "",
                        dialogue=p.get("dialogue"),
                        shot_type=p.get("shot_type") or "MS",
                        camera_angle=p.get("camera_angle") or "eye-level",
                        emotion=p.get("emotion"),
                        composition=p.get("composition"),
                        temp_image_url=p.get("temp_image_url") or p.get("image_url"),
                    ))
                except Exception as e:
                    warnings.append(f"conversation panel #{i} skipped: {e}")

        if needs_chars and ctype == "characters":
            raw = card.get("characters", []) or []
            for c in raw:
                if not isinstance(c, dict) or not c.get("name"):
                    continue
                try:
                    characters.append(AgentCharacter(
                        name=str(c["name"]),
                        visual_prompt=c.get("visual_prompt"),
                        temp_image_url=c.get("temp_image_url") or c.get("image_url"),
                        appearance_traits=list(c.get("appearance_traits") or []),
                        personality_traits=list(c.get("personality_traits") or []),
                        wardrobe_notes=c.get("wardrobe_notes"),
                    ))
                except Exception as e:
                    warnings.append(f"conversation character skipped: {e}")

        if needs_scenes and ctype == "scenes":
            raw = card.get("scenes", []) or []
            for s in raw:
                if not isinstance(s, dict) or not s.get("name"):
                    continue
                try:
                    scenes.append(AgentScene(
                        name=str(s["name"]),
                        visual_prompt=s.get("visual_prompt"),
                        temp_image_url=s.get("temp_image_url") or s.get("image_url"),
                        time_of_day=s.get("time_of_day"),
                        weather=s.get("weather"),
                        mood=s.get("mood"),
                    ))
                except Exception as e:
                    warnings.append(f"conversation scene skipped: {e}")

        if needs_style and ctype == "art_style":
            art_style = AgentArtStyle(
                base_style=str(card.get("base_style") or ""),
                color_tone=str(card.get("color_tone") or ""),
                atmosphere=str(card.get("atmosphere") or ""),
            )

    enriched = req.model_copy(update={
        "panels": panels if needs_panels and panels else req.panels,
        "characters": characters if needs_chars and characters else req.characters,
        "scenes": scenes if needs_scenes and scenes else req.scenes,
        "art_style": art_style,
    })
    return enriched, warnings
```

**Note on card-type names:** The card types `"panels"`, `"characters"`, `"scenes"`, `"art_style"` are **guesses based on convention**. If the actual card types differ in the real data (e.g., the existing `outline` card already uses a different key name), the implementer MUST grep `entities_json` usage in `apps/api/app/api/routes/agent.py` and `apps/web/src/components/chat/` to confirm. If the card types are different, adjust the string literals in this file to match. Do NOT rename Python field names — adjust only the `card.get("type")` comparison strings.

- [ ] **Step 3: Write tests**

```python
"""Tests for agent_commit.conversation_reader."""
import uuid
import pytest
from datetime import datetime

from app.schemas.agent_commit import CommitToStudioRequest


@pytest.fixture
def seeded_conv(test_client):
    import os; os.environ["ENABLE_AUTH"] = "false"
    from app.core.database import SessionLocal
    from app.models.conversation import Conversation
    from app.models.conversation_message import ConversationMessage

    db = SessionLocal()
    try:
        conv_id = str(uuid.uuid4())
        db.add(Conversation(id=conv_id))  # adjust fields if Conversation model requires more

        msgs = [
            ConversationMessage(
                id=str(uuid.uuid4()), conversation_id=conv_id, role="assistant",
                content="characters card",
                entities_json={"card": {"type": "characters", "characters": [
                    {"name": "Alice", "visual_prompt": "a girl", "temp_image_url": "http://x/a.png"},
                    {"name": "Bob"},
                ]}},
            ),
            ConversationMessage(
                id=str(uuid.uuid4()), conversation_id=conv_id, role="assistant",
                content="scenes card",
                entities_json={"card": {"type": "scenes", "scenes": [
                    {"name": "Rooftop", "time_of_day": "sunset"},
                ]}},
            ),
            ConversationMessage(
                id=str(uuid.uuid4()), conversation_id=conv_id, role="assistant",
                content="panels card",
                entities_json={"card": {"type": "panels", "episode_number": 1, "panels": [
                    {"id": "p1", "order": 0, "scene_name": "Rooftop",
                     "characters": ["Alice"], "scene_description": "wait", "temp_image_url": "http://x/p1.png"},
                    {"id": "p2", "order": 1, "scene_name": "Rooftop",
                     "characters": ["Alice", "Bob"], "scene_description": "meet"},
                ]}},
            ),
            ConversationMessage(
                id=str(uuid.uuid4()), conversation_id=conv_id, role="assistant",
                content="style card",
                entities_json={"card": {"type": "art_style",
                                        "base_style": "Korean webtoon", "color_tone": "warm",
                                        "atmosphere": "romantic"}},
            ),
        ]
        db.add_all(msgs); db.commit()
        return {"conversation_id": conv_id}
    finally:
        db.close()


def test_enriches_empty_request_from_conversation(seeded_conv):
    from app.core.database import SessionLocal
    from app.services.agent_commit.conversation_reader import enrich_request_from_conversation

    db = SessionLocal()
    try:
        req = CommitToStudioRequest(conversation_id=seeded_conv["conversation_id"], episode_number=1)
        enriched, warnings = enrich_request_from_conversation(db, req)
        assert len(enriched.panels) == 2
        assert enriched.panels[0].scene_name == "Rooftop"
        assert len(enriched.characters) == 2
        assert {c.name for c in enriched.characters} == {"Alice", "Bob"}
        assert len(enriched.scenes) == 1 and enriched.scenes[0].name == "Rooftop"
        assert enriched.art_style.base_style == "Korean webtoon"
        assert warnings == []
    finally:
        db.close()


def test_preserves_request_fields_if_present(seeded_conv):
    from app.core.database import SessionLocal
    from app.services.agent_commit.conversation_reader import enrich_request_from_conversation
    from app.schemas.agent_commit import AgentCharacter

    db = SessionLocal()
    try:
        req = CommitToStudioRequest(
            conversation_id=seeded_conv["conversation_id"], episode_number=1,
            characters=[AgentCharacter(name="PreSet")],
        )
        enriched, _ = enrich_request_from_conversation(db, req)
        # Characters NOT overwritten because request supplied its own
        assert [c.name for c in enriched.characters] == ["PreSet"]
        # Panels still enriched
        assert len(enriched.panels) == 2
    finally:
        db.close()


def test_no_cards_returns_empty_request_unchanged(test_client):
    import os; os.environ["ENABLE_AUTH"] = "false"
    from app.core.database import SessionLocal
    from app.models.conversation import Conversation
    from app.services.agent_commit.conversation_reader import enrich_request_from_conversation

    db = SessionLocal()
    try:
        empty_conv_id = str(uuid.uuid4())
        db.add(Conversation(id=empty_conv_id))
        db.commit()

        req = CommitToStudioRequest(conversation_id=empty_conv_id, episode_number=1)
        enriched, warnings = enrich_request_from_conversation(db, req)
        assert len(enriched.panels) == 0
        assert len(enriched.characters) == 0
        assert warnings == []
    finally:
        db.close()


def test_wrong_episode_number_doesnt_pick_panels(seeded_conv):
    from app.core.database import SessionLocal
    from app.services.agent_commit.conversation_reader import enrich_request_from_conversation

    db = SessionLocal()
    try:
        req = CommitToStudioRequest(conversation_id=seeded_conv["conversation_id"], episode_number=99)
        enriched, _ = enrich_request_from_conversation(db, req)
        assert len(enriched.panels) == 0  # no panels for episode 99
        # But characters and scenes are episode-agnostic in current schema, so still filled
        assert len(enriched.characters) == 2
    finally:
        db.close()
```

**Note:** If `Conversation` or `ConversationMessage` models have required non-null fields that the fixture doesn't set (e.g., `project_id`, `user_id`, timestamps with no defaults), the test will fail at insert. The implementer should inspect the models and add required fields. If the model requires a `project_id`, create a Project in the fixture too. Do NOT change the test logic — only fill the fixture with whatever required fields exist.

- [ ] **Step 4: Run** `cd apps/api && pytest tests/unit/services/test_agent_conversation_reader.py -v` → 4 pass

If card-type strings need adjusting based on Step 1 investigation, tweak both the reader and the test fixtures to match.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/agent_commit/conversation_reader.py \
        apps/api/tests/unit/services/test_agent_conversation_reader.py
git commit -m "feat(api): agent_commit conversation_reader (lean payload fallback)"
```

---

## Task 9: Commit orchestrator (uses conversation_reader)

**Files:** Create `apps/api/app/services/agent_commit/commit_orchestrator.py` + update `__init__.py`

- [ ] **Step 1: Write the orchestrator**

```python
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

        panel = Panel(
            id=panel_id, chapter_id=chapter.id,
            order_index=agent_panel.order if agent_panel.order else idx,
            title=f"Panel {idx + 1}",
            summary=agent_panel.scene_description[:255] if agent_panel.scene_description else None,
            spec_json=spec, render_status="draft", preview_url=preview_key,
        )
        db.add(panel)

    db.flush()
    refresh_chapter_bindings(db, chapter.id)

    return CommitResult(
        chapter, "created",
        len(req.characters), len(req.scenes), len(req.panels),
        warnings, payload_source,
    )
```

- [ ] **Step 2: Update `__init__.py` to re-export**

Overwrite `apps/api/app/services/agent_commit/__init__.py`:

```python
"""Agent commit-to-studio service."""
from app.services.agent_commit.commit_orchestrator import (
    CommitResult, commit_agent_to_studio,
)
from app.services.agent_commit.idempotency import find_existing_chapter
from app.services.agent_commit.conversation_reader import enrich_request_from_conversation

__all__ = [
    "CommitResult",
    "commit_agent_to_studio",
    "find_existing_chapter",
    "enrich_request_from_conversation",
]
```

- [ ] **Step 3: Verify**

`cd apps/api && python -c "from app.services.agent_commit import commit_agent_to_studio; print('ok')"`

- [ ] **Step 4: Commit**

```bash
git add apps/api/app/services/agent_commit/
git commit -m "feat(api): agent_commit orchestrator with conversation_reader fallback"
```

---

## Task 10: Commit endpoint

**Files:** Modify `apps/api/app/api/routes/agent.py` — append new route.

- [ ] **Step 1: Add imports (merge; do NOT duplicate)**

```python
from app.schemas.agent_commit import CommitToStudioRequest, CommitToStudioResponse, CommitCreatedCounts
from app.services.agent_commit import commit_agent_to_studio
from app.models.project import Project
from app.api.deps import get_current_user
from app.models.user import User
from app.core.database import get_db
```

- [ ] **Step 2: Append route at end of file (or near other `/projects/*` routes)**

```python
@router.post(
    "/projects/{project_id}/commit-to-studio",
    response_model=CommitToStudioResponse,
)
async def commit_to_studio(
    project_id: str,
    req: CommitToStudioRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Commit Agent conversation outputs to Studio — creates Chapter + Panels + Assets.

    Accepts either a full payload (frontend has the data) or a lean payload
    (just {conversation_id, episode_number, [title, summary]}); in the lean case
    the backend reads ConversationMessage cards to fill in the rest.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    owner_id = getattr(project, "owner_id", None)
    if owner_id and getattr(current_user, "id", None) and owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this project")

    try:
        result = await commit_agent_to_studio(db, project_id, req)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"commit-to-studio failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Commit failed: {e}")

    return CommitToStudioResponse(
        chapter_id=result.chapter.id,
        chapter_title=result.chapter.title,
        status=result.status,
        created_assets=CommitCreatedCounts(
            characters=result.character_count,
            scenes=result.scene_count,
        ),
        created_panels=result.panel_count,
        studio_url=f"/projects/{project_id}/chapters/{result.chapter.id}/studio",
        warnings=result.warnings,
        payload_source=result.payload_source,
    )
```

- [ ] **Step 3: Verify registered**

```bash
cd apps/api && python -c "from app.main import app; [print(r.methods, r.path) for r in app.routes if 'commit-to-studio' in r.path]"
```
Expected: `{'POST'} /api/v1/agent/projects/{project_id}/commit-to-studio`

- [ ] **Step 4: Commit**

```bash
git add apps/api/app/api/routes/agent.py
git commit -m "feat(api): POST /agent/projects/{pid}/commit-to-studio (full or lean payload)"
```

---

## Task 11: Commit endpoint integration tests

**Files:** Create `apps/api/tests/unit/routes/test_agent_commit.py`

- [ ] **Step 1: Write tests**

```python
"""Integration tests for POST /api/v1/agent/projects/{pid}/commit-to-studio."""
import uuid
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def seeded(test_client: TestClient):
    import os; os.environ["ENABLE_AUTH"] = "false"
    from app.core.database import SessionLocal
    from app.models.project import Project

    db = SessionLocal()
    try:
        proj = Project(id=str(uuid.uuid4()), name="AC", description="")
        db.add(proj); db.commit()
        return {"project_id": proj.id}
    finally:
        db.close()


@pytest.fixture
def seeded_with_conv(seeded):
    """project + conversation with full set of cards for lean-payload tests."""
    from app.core.database import SessionLocal
    from app.models.conversation import Conversation
    from app.models.conversation_message import ConversationMessage

    db = SessionLocal()
    try:
        conv_id = str(uuid.uuid4())
        db.add(Conversation(id=conv_id))
        db.add_all([
            ConversationMessage(
                id=str(uuid.uuid4()), conversation_id=conv_id, role="assistant",
                content="chars", entities_json={"card": {"type": "characters", "characters": [
                    {"name": "Alice", "temp_image_url": "http://t/a.png"},
                    {"name": "Bob", "temp_image_url": "http://t/b.png"},
                ]}}),
            ConversationMessage(
                id=str(uuid.uuid4()), conversation_id=conv_id, role="assistant",
                content="scenes", entities_json={"card": {"type": "scenes", "scenes": [
                    {"name": "Rooftop", "temp_image_url": "http://t/s.png", "time_of_day": "sunset"},
                ]}}),
            ConversationMessage(
                id=str(uuid.uuid4()), conversation_id=conv_id, role="assistant",
                content="panels", entities_json={"card": {"type": "panels", "episode_number": 1, "panels": [
                    {"id": "p1", "order": 0, "scene_name": "Rooftop", "characters": ["Alice"],
                     "scene_description": "wait", "temp_image_url": "http://t/p1.png"},
                    {"id": "p2", "order": 1, "scene_name": "Rooftop", "characters": ["Alice", "Bob"],
                     "scene_description": "meet"},
                ]}}),
        ])
        db.commit()
        return {**seeded, "conversation_id": conv_id}
    finally:
        db.close()


def make_full_body(conversation_id="c1", episode_number=1, with_images=True):
    img = "http://example.com/img.png" if with_images else None
    return {
        "conversation_id": conversation_id,
        "episode_number": episode_number,
        "episode_title": "初遇",
        "outline_summary": "相遇",
        "art_style": {"base_style": "Korean webtoon", "color_tone": "warm", "atmosphere": "romantic"},
        "characters": [
            {"name": "Alice", "temp_image_url": img, "appearance_traits": ["short hair"], "personality_traits": []},
            {"name": "Bob", "temp_image_url": img, "appearance_traits": [], "personality_traits": []},
        ],
        "scenes": [
            {"name": "Rooftop", "temp_image_url": img, "time_of_day": "sunset", "weather": "clear"},
        ],
        "panels": [
            {"id": "ap-1", "order": 0, "scene_name": "Rooftop", "characters": ["Alice"],
             "scene_description": "she waits", "shot_type": "MS", "camera_angle": "eye-level", "temp_image_url": img},
            {"id": "ap-2", "order": 1, "scene_name": "Rooftop", "characters": ["Alice", "Bob"],
             "scene_description": "they meet", "shot_type": "MCU", "camera_angle": "high-angle", "temp_image_url": img},
        ],
    }


class TestCommitToStudioFullPayload:
    def test_creates_chapter_panels_assets(self, test_client, seeded):
        from app.core.database import SessionLocal
        from app.models.chapter import Chapter
        from app.models.panel import Panel
        from app.models.asset import Asset

        with patch("app.services.agent_commit.commit_orchestrator.fetch_and_persist",
                   new=AsyncMock(return_value="key/p.png")), \
             patch("app.services.agent_commit.asset_sync.fetch_and_persist",
                   new=AsyncMock(return_value="key/a.png")):
            resp = test_client.post(
                f"/api/v1/agent/projects/{seeded['project_id']}/commit-to-studio",
                json=make_full_body(),
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "created"
        assert body["created_panels"] == 2
        assert body["created_assets"]["characters"] == 2
        assert body["created_assets"]["scenes"] == 1
        assert body["payload_source"] == "request"

        db = SessionLocal()
        try:
            ch = db.query(Chapter).filter(Chapter.id == body["chapter_id"]).first()
            assert ch.layout_json["source"]["type"] == "agent"
            panels = db.query(Panel).filter(Panel.chapter_id == ch.id).all()
            assert len(panels) == 2 and all(p.preview_url == "key/p.png" for p in panels)
            spec0 = panels[0].spec_json
            assert spec0["characters"][0]["asset_id"]
            assert spec0["scene"].get("anchor_id")
            assets = db.query(Asset).filter(Asset.project_id == seeded["project_id"]).all()
            assert {a.name for a in assets} == {"Alice", "Bob", "Rooftop"}
            for a in assets:
                assert a.data_json["created_via"] == "agent"
        finally:
            db.close()

    def test_idempotent_second_call(self, test_client, seeded):
        from app.core.database import SessionLocal
        from app.models.chapter import Chapter

        with patch("app.services.agent_commit.commit_orchestrator.fetch_and_persist",
                   new=AsyncMock(return_value="k")), \
             patch("app.services.agent_commit.asset_sync.fetch_and_persist",
                   new=AsyncMock(return_value="k")):
            r1 = test_client.post(
                f"/api/v1/agent/projects/{seeded['project_id']}/commit-to-studio", json=make_full_body())
            r2 = test_client.post(
                f"/api/v1/agent/projects/{seeded['project_id']}/commit-to-studio", json=make_full_body())
        assert r1.json()["status"] == "created"
        assert r2.json()["status"] == "already_exists"
        assert r1.json()["chapter_id"] == r2.json()["chapter_id"]

        db = SessionLocal()
        try:
            count = db.query(Chapter).filter(Chapter.project_id == seeded["project_id"]).count()
            assert count == 1
        finally:
            db.close()

    def test_image_download_failure_produces_warning(self, test_client, seeded):
        from app.services.agent_commit.image_fetcher import ImageFetchError

        with patch("app.services.agent_commit.commit_orchestrator.fetch_and_persist",
                   new=AsyncMock(side_effect=ImageFetchError("404"))), \
             patch("app.services.agent_commit.asset_sync.fetch_and_persist",
                   new=AsyncMock(side_effect=ImageFetchError("404"))):
            resp = test_client.post(
                f"/api/v1/agent/projects/{seeded['project_id']}/commit-to-studio",
                json=make_full_body(),
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "created"
        assert len(body["warnings"]) > 0

    def test_project_not_found(self, test_client):
        resp = test_client.post(
            "/api/v1/agent/projects/does-not-exist/commit-to-studio",
            json=make_full_body(),
        )
        assert resp.status_code == 404

    def test_reuses_existing_asset_by_name(self, test_client, seeded):
        from app.core.database import SessionLocal
        from app.models.asset import Asset

        db = SessionLocal()
        existing = Asset(id=str(uuid.uuid4()), project_id=seeded["project_id"],
                         type="character", name="Alice", data_json={"created_via": "studio"})
        db.add(existing); db.commit(); existing_id = existing.id; db.close()

        with patch("app.services.agent_commit.commit_orchestrator.fetch_and_persist",
                   new=AsyncMock(return_value="k")), \
             patch("app.services.agent_commit.asset_sync.fetch_and_persist",
                   new=AsyncMock(return_value="k")):
            resp = test_client.post(
                f"/api/v1/agent/projects/{seeded['project_id']}/commit-to-studio",
                json=make_full_body(),
            )
        assert resp.status_code == 200

        db = SessionLocal()
        try:
            alice_assets = db.query(Asset).filter(
                Asset.project_id == seeded["project_id"],
                Asset.type == "character", Asset.name == "Alice",
            ).all()
            assert len(alice_assets) == 1 and alice_assets[0].id == existing_id
            assert alice_assets[0].data_json["created_via"] == "studio"
        finally:
            db.close()


class TestCommitToStudioLeanPayload:
    def test_lean_payload_populates_from_conversation(self, test_client, seeded_with_conv):
        from app.core.database import SessionLocal
        from app.models.panel import Panel
        from app.models.asset import Asset

        with patch("app.services.agent_commit.commit_orchestrator.fetch_and_persist",
                   new=AsyncMock(return_value="k/p.png")), \
             patch("app.services.agent_commit.asset_sync.fetch_and_persist",
                   new=AsyncMock(return_value="k/a.png")):
            resp = test_client.post(
                f"/api/v1/agent/projects/{seeded_with_conv['project_id']}/commit-to-studio",
                json={
                    "conversation_id": seeded_with_conv["conversation_id"],
                    "episode_number": 1,
                    "episode_title": "初遇",
                },
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "created"
        assert body["created_panels"] == 2
        assert body["created_assets"]["characters"] == 2
        assert body["created_assets"]["scenes"] == 1
        assert body["payload_source"] == "conversation"

        db = SessionLocal()
        try:
            panels = db.query(Panel).filter(Panel.chapter_id == body["chapter_id"]).all()
            assert len(panels) == 2
            assets = db.query(Asset).filter(Asset.project_id == seeded_with_conv["project_id"]).all()
            assert {a.name for a in assets} == {"Alice", "Bob", "Rooftop"}
        finally:
            db.close()
```

- [ ] **Step 2: Run** `cd apps/api && pytest tests/unit/routes/test_agent_commit.py -v` → 6 pass

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/unit/routes/test_agent_commit.py
git commit -m "test(api): cover commit-to-studio full + lean payload paths"
```

---

## Task 12: Frontend agentApi.commitToStudio

**Files:** Modify `apps/web/src/lib/api/services.ts`

- [ ] **Step 1: Locate or create `agentApi` export**

Search for `export const agentApi`. If it exists, extend; else append.

- [ ] **Step 2: Add method**

```ts
    commitToStudio: (
        projectId: string,
        payload: {
            conversation_id: string
            episode_number: number
            episode_title?: string
            outline_summary?: string
            art_style?: { base_style?: string; color_tone?: string; atmosphere?: string }
            characters?: Array<Record<string, unknown>>
            scenes?: Array<Record<string, unknown>>
            panels?: Array<Record<string, unknown>>
        }
    ) =>
        apiPost<{
            chapter_id: string
            chapter_title: string
            status: 'created' | 'already_exists'
            created_assets: { characters: number; scenes: number }
            created_panels: number
            studio_url: string
            warnings: string[]
            payload_source: 'request' | 'conversation'
        }>(`/api/v1/agent/projects/${projectId}/commit-to-studio`, payload),
```

- [ ] **Step 3: Typecheck + commit**

```bash
cd apps/web && npx tsc --noEmit
git add apps/web/src/lib/api/services.ts
git commit -m "feat(web): agentApi.commitToStudio method"
```

---

## Task 13: Open-in-Studio button on episode DETAIL page (full payload)

**Files:** Modify `apps/web/src/app/agent/[projectId]/episodes/[episodeNum]/page.tsx`

- [ ] **Step 1: Read the detail page in full**

Understand the existing state shape — where are `panels`, `characters`, `scenes`, `art_style`, and `mainConvId` (or equivalent conversation id) stored? Grep for "panels" / "characters" / "art_style" in the file to find the data flow.

- [ ] **Step 2: Add handler**

```tsx
import { useRouter } from 'next/navigation'
import { agentApi } from '@/lib/api/services'
import { useToast } from '@/hooks/use-toast'
import { Loader2, Play } from 'lucide-react'

// inside component:
const { toast } = useToast()
const router = useRouter()
const [committing, setCommitting] = useState(false)

const handleOpenInStudio = useCallback(async () => {
    if (!conversationId) {
        toast({ title: '缺少对话上下文', variant: 'destructive' })
        return
    }
    setCommitting(true)
    try {
        const payload = {
            conversation_id: conversationId,
            episode_number: episodeNum,
            episode_title: episodeTitle ?? '',
            outline_summary: episodeSummary ?? '',
            art_style: artStyle ?? {},
            characters: (characters ?? []).map(c => ({
                name: c.name,
                visual_prompt: c.visual_prompt ?? c.description ?? '',
                temp_image_url: c.image_url ?? c.temp_image_url,
                appearance_traits: c.appearance_traits ?? [],
                personality_traits: c.personality_traits ?? [],
                wardrobe_notes: c.wardrobe_notes,
            })),
            scenes: (scenes ?? []).map(s => ({
                name: s.name,
                visual_prompt: s.visual_prompt ?? s.description ?? '',
                temp_image_url: s.image_url ?? s.temp_image_url,
                time_of_day: s.time_of_day,
                weather: s.weather,
                mood: s.mood,
            })),
            panels: (panels ?? []).map(p => ({
                id: p.id,
                order: p.order ?? p.index ?? 0,
                scene_name: p.scene_name ?? p.scene,
                characters: p.characters ?? [],
                scene_description: p.scene_description ?? p.description ?? '',
                dialogue: p.dialogue,
                shot_type: p.shot_type ?? 'MS',
                camera_angle: p.camera_angle ?? 'eye-level',
                emotion: p.emotion,
                composition: p.composition,
                temp_image_url: p.image_url ?? p.temp_image_url,
            })),
        }
        const result = await agentApi.commitToStudio(projectId, payload)
        if (result.status === 'already_exists') {
            toast({ title: '已打开已有章节', description: result.chapter_title })
        } else {
            toast({
                title: '已创建章节',
                description: `${result.created_panels} 分镜 · ${result.created_assets.characters} 角色 · ${result.created_assets.scenes} 场景`,
            })
            if (result.warnings.length > 0) {
                toast({
                    title: '部分图片未能保存',
                    description: `${result.warnings.length} 条警告，可在 Studio 手动上传`,
                })
            }
        }
        router.push(result.studio_url)
    } catch (err) {
        toast({
            title: '提交失败',
            description: err instanceof Error ? err.message : String(err),
            variant: 'destructive',
        })
    } finally {
        setCommitting(false)
    }
}, [conversationId, episodeNum, episodeTitle, episodeSummary, artStyle,
    characters, scenes, panels, projectId, router, toast])
```

**IMPORTANT:** The variable names `conversationId`, `episodeTitle`, `episodeSummary`, `artStyle`, `characters`, `scenes`, `panels` are placeholders — use whatever the actual page state fields are. If panel data uses nested structure like `episode.panels`, flatten in the payload mapper. If there is NO conversation id in state, get it from the URL params (`useSearchParams().get('conversation')`) or from a `conversationsApi.listByProject` lookup like the list page does.

- [ ] **Step 3: Add button to the page UI**

Place in the top action bar of the episode detail page:

```tsx
<Button
    onClick={handleOpenInStudio}
    disabled={committing || (panels?.length ?? 0) === 0}
    size="lg"
>
    {committing
        ? (<><Loader2 className="w-4 h-4 mr-2 animate-spin" /> 提交中…</>)
        : (<><Play className="w-4 h-4 mr-2" /> 在 Studio 打开</>)}
</Button>
```

- [ ] **Step 4: Typecheck + smoke**

`cd apps/web && npx tsc --noEmit`

Navigate to `/agent/<pid>/episodes/1` after conversing; click the button; verify redirect to Studio with panels visible.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/app/agent/[projectId]/episodes/[episodeNum]/page.tsx
git commit -m "feat(web): Open-in-Studio button on episode detail (full payload)"
```

---

## Task 14: Bulk commit button on episode LIST page (lean payload)

**Files:** Modify `apps/web/src/app/agent/[projectId]/episodes/page.tsx`

- [ ] **Step 1: Read the list page (242 lines) and find where `mainConv` is computed**

The list page already calls `conversationsApi.listByProject` and picks `mainConv` — we need its id. Lift `mainConv.id` into state:

```tsx
const [mainConvId, setMainConvId] = useState<string | null>(null)

// inside loadProjectAndEpisodes, after finding mainConv:
setMainConvId(mainConv.id)
```

- [ ] **Step 2: Add bulk handler**

```tsx
import { agentApi } from '@/lib/api/services'
import { useToast } from '@/hooks/use-toast'

const { toast } = useToast()
const [bulkProgress, setBulkProgress] = useState<{ done: number; total: number } | null>(null)

const handleCommitAll = useCallback(async () => {
    if (!mainConvId) {
        toast({ title: '缺少对话上下文', variant: 'destructive' })
        return
    }
    setBulkProgress({ done: 0, total: episodes.length })
    const failures: number[] = []

    for (let i = 0; i < episodes.length; i++) {
        const ep = episodes[i]
        try {
            await agentApi.commitToStudio(projectId, {
                // Lean payload: backend reads conversation to fill in panels/characters/scenes
                conversation_id: mainConvId,
                episode_number: ep.number,
                episode_title: ep.title ?? '',
                outline_summary: ep.summary ?? '',
            })
        } catch (e) {
            failures.push(ep.number)
            toast({
                title: `第${ep.number}集提交失败`,
                description: e instanceof Error ? e.message : String(e),
                variant: 'destructive',
            })
        }
        setBulkProgress({ done: i + 1, total: episodes.length })
    }

    setBulkProgress(null)
    if (failures.length === 0) {
        toast({ title: '全部提交完成', description: `已处理 ${episodes.length} 集` })
    } else {
        toast({
            title: `${episodes.length - failures.length}/${episodes.length} 成功`,
            description: `失败: 第 ${failures.join(', ')} 集`,
            variant: 'destructive',
        })
    }
}, [episodes, mainConvId, projectId, toast])
```

- [ ] **Step 3: Add button to page header**

Near the existing page title row:

```tsx
<Button
    onClick={handleCommitAll}
    disabled={!mainConvId || bulkProgress !== null || episodes.length === 0}
    variant="secondary"
>
    {bulkProgress
        ? `提交中 ${bulkProgress.done}/${bulkProgress.total}`
        : '一键提交全部到 Studio'}
</Button>
```

Also add a per-card small button that navigates to the detail page (where single-episode full commit lives):

```tsx
<Button
    size="sm"
    variant="outline"
    onClick={() => router.push(`/agent/${projectId}/episodes/${episode.number}`)}
>
    打开详情
</Button>
```

- [ ] **Step 4: Typecheck + smoke**

`cd apps/web && npx tsc --noEmit`

Start dev server; navigate to `/agent/<pid>/episodes`; verify bulk button works (check backend creates N chapters); verify "打开详情" button navigates to detail page.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/app/agent/[projectId]/episodes/page.tsx
git commit -m "feat(web): bulk commit all episodes (lean payload) on episode list"
```

---

## Task 15: ChatProjectPicker component

**Files:** Create `apps/web/src/components/chat/ChatProjectPicker.tsx`

- [ ] **Step 1: Write the component**

```tsx
'use client'

import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
    DropdownMenu, DropdownMenuContent, DropdownMenuItem,
    DropdownMenuTrigger, DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ChevronDown, Plus, Search } from 'lucide-react'
import { projectsApi } from '@/lib/api/services'
import type { Project } from '@/lib/api/types'

export interface ChatProjectPickerProps {
    currentProjectId: string
    onCreateNew?: () => void
}

export function ChatProjectPicker({ currentProjectId, onCreateNew }: ChatProjectPickerProps) {
    const router = useRouter()
    const [projects, setProjects] = useState<Project[]>([])
    const [open, setOpen] = useState(false)
    const [query, setQuery] = useState('')

    useEffect(() => {
        if (!open) return
        projectsApi.list?.().then((data: any) => {
            const items = Array.isArray(data) ? data : (data?.items ?? [])
            setProjects(items)
        }).catch(() => {})
    }, [open])

    const current = projects.find(p => p.id === currentProjectId)
    const filtered = useMemo(() => {
        const q = query.trim().toLowerCase()
        if (!q) return projects
        return projects.filter(p => p.name.toLowerCase().includes(q))
    }, [projects, query])

    return (
        <DropdownMenu open={open} onOpenChange={setOpen}>
            <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="gap-2">
                    <span className="truncate max-w-[200px]">{current?.name ?? '选择项目'}</span>
                    <ChevronDown className="w-4 h-4" />
                </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-[280px]">
                <div className="p-2">
                    <div className="relative">
                        <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                        <Input
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            placeholder="搜索项目…"
                            className="pl-8"
                            aria-label="搜索项目"
                        />
                    </div>
                </div>
                <DropdownMenuSeparator />
                <div className="max-h-[320px] overflow-y-auto">
                    {filtered.length === 0 ? (
                        <div className="px-3 py-6 text-center text-sm text-muted-foreground">
                            {query ? '无匹配项目' : '还没有项目'}
                        </div>
                    ) : filtered.map(p => (
                        <DropdownMenuItem
                            key={p.id}
                            onSelect={() => { setOpen(false); router.push(`/chat/${p.id}`) }}
                            className={p.id === currentProjectId ? 'bg-accent' : ''}
                        >
                            <div className="flex flex-col gap-0.5 min-w-0">
                                <span className="truncate text-sm">{p.name}</span>
                                {p.description ? (
                                    <span className="truncate text-xs text-muted-foreground">{p.description}</span>
                                ) : null}
                            </div>
                        </DropdownMenuItem>
                    ))}
                </div>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={onCreateNew ?? (() => router.push('/projects?create=1'))}>
                    <Plus className="w-4 h-4 mr-2" />
                    新建项目
                </DropdownMenuItem>
            </DropdownMenuContent>
        </DropdownMenu>
    )
}
```

- [ ] **Step 2: Typecheck + commit**

```bash
cd apps/web && npx tsc --noEmit
git add apps/web/src/components/chat/ChatProjectPicker.tsx
git commit -m "feat(web): ChatProjectPicker dropdown"
```

---

## Task 16: ChatEmptyState component

**Files:** Create `apps/web/src/components/chat/ChatEmptyState.tsx`

- [ ] **Step 1: Write the component**

```tsx
'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { MessageSquarePlus, FolderPlus, ArrowRight } from 'lucide-react'
import { projectsApi } from '@/lib/api/services'
import type { Project } from '@/lib/api/types'

export function ChatEmptyState() {
    const router = useRouter()
    const [recent, setRecent] = useState<Project[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        projectsApi.list?.()
            .then((data: any) => {
                const items = Array.isArray(data) ? data : (data?.items ?? [])
                setRecent(items.slice(0, 6))
            })
            .finally(() => setLoading(false))
    }, [])

    if (loading) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-500" />
            </div>
        )
    }

    if (recent.length === 0) {
        return (
            <div className="flex items-center justify-center h-full p-8">
                <Card className="max-w-md">
                    <CardHeader>
                        <div className="mb-3 inline-flex items-center justify-center w-12 h-12 rounded-full bg-emerald-500/10">
                            <MessageSquarePlus className="w-6 h-6 text-emerald-500" />
                        </div>
                        <CardTitle>开始你的第一个项目</CardTitle>
                        <CardDescription>
                            Agent 对话模式让你通过聊天创作 webtoon。先创建一个项目作为承载。
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <Button onClick={() => router.push('/projects?create=1')} className="w-full">
                            <FolderPlus className="w-4 h-4 mr-2" />
                            创建项目
                        </Button>
                    </CardContent>
                </Card>
            </div>
        )
    }

    return (
        <div className="max-w-3xl mx-auto p-8">
            <div className="mb-6">
                <h2 className="text-2xl font-semibold">选择项目开始对话</h2>
                <p className="text-sm text-muted-foreground mt-1">或者创建一个新项目</p>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
                {recent.map(p => (
                    <Card
                        key={p.id}
                        onClick={() => router.push(`/chat/${p.id}`)}
                        className="cursor-pointer hover:bg-accent/50 transition-colors"
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                                e.preventDefault()
                                router.push(`/chat/${p.id}`)
                            }
                        }}
                    >
                        <CardHeader>
                            <CardTitle className="text-base truncate">{p.name}</CardTitle>
                            {p.description ? (
                                <CardDescription className="line-clamp-2">{p.description}</CardDescription>
                            ) : null}
                        </CardHeader>
                        <CardContent>
                            <div className="text-xs text-emerald-500 inline-flex items-center">
                                开始对话 <ArrowRight className="w-3 h-3 ml-1" />
                            </div>
                        </CardContent>
                    </Card>
                ))}
                <Card
                    onClick={() => router.push('/projects?create=1')}
                    className="cursor-pointer border-dashed hover:bg-accent/50 transition-colors flex items-center justify-center p-8"
                    role="button" tabIndex={0}
                >
                    <div className="text-center">
                        <FolderPlus className="w-8 h-8 mx-auto mb-2 text-muted-foreground" />
                        <div className="text-sm">新建项目</div>
                    </div>
                </Card>
            </div>
        </div>
    )
}
```

- [ ] **Step 2: Typecheck + commit**

```bash
cd apps/web && npx tsc --noEmit
git add apps/web/src/components/chat/ChatEmptyState.tsx
git commit -m "feat(web): ChatEmptyState"
```

---

## Task 17: /chat landing refactor

**Files:** Modify `apps/web/src/app/chat/page.tsx` (completely rewrite)

- [ ] **Step 1: Replace contents**

```tsx
/** Chat landing — /chat with no project selected. */
'use client'

import { ChatEmptyState } from '@/components/chat/ChatEmptyState'

export default function ChatLandingPage() {
    return (
        <div className="h-screen flex flex-col bg-background">
            <nav className="border-b px-6 py-3 flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <h1 className="text-xl font-bold">AI Webtoon Studio</h1>
                    <span className="text-sm text-muted-foreground">Chat Mode</span>
                </div>
            </nav>
            <div className="flex-1 overflow-y-auto">
                <ChatEmptyState />
            </div>
        </div>
    )
}
```

- [ ] **Step 2: Typecheck + smoke**

`cd apps/web && npx tsc --noEmit`. Visit `/chat` — should see empty state or recent-projects grid (not the old demo-project chat).

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/app/chat/page.tsx
git commit -m "feat(web): /chat is now project landing (no demo-project hardcode)"
```

---

## Task 18: /chat/[projectId]/page.tsx new route

**Files:** Create `apps/web/src/app/chat/[projectId]/page.tsx`

- [ ] **Step 1: Write the page**

```tsx
/** Chat page scoped to a specific project. */
'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import { ChatPanel } from '@/components/chat'
import { ChatProjectPicker } from '@/components/chat/ChatProjectPicker'
import { Button } from '@/components/ui/button'
import { projectsApi } from '@/lib/api/services'

function generateId(): string { return crypto.randomUUID() }

export default function ChatProjectPage() {
    const params = useParams()
    const router = useRouter()
    const searchParams = useSearchParams()
    const projectId = params.projectId as string

    const [conversationId, setConversationId] = useState<string | null>(null)
    const [, setProjectName] = useState<string>('')
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        if (!projectId) return
        projectsApi.get(projectId)
            .then((p: any) => setProjectName(p?.name ?? ''))
            .catch((e) => {
                const status = e?.status ?? 0
                if (status === 404) setError('项目不存在')
                else if (status === 403) setError('无权访问此项目')
                else setError('加载项目失败')
            })
    }, [projectId])

    useEffect(() => {
        const fromUrl = searchParams.get('conversation')
        setConversationId(fromUrl || generateId())
    }, [searchParams])

    if (error) {
        return (
            <div className="h-screen flex items-center justify-center flex-col gap-4">
                <p className="text-lg">{error}</p>
                <Button variant="outline" onClick={() => router.push('/chat')}>返回项目列表</Button>
            </div>
        )
    }

    if (!conversationId) {
        return (
            <div className="flex items-center justify-center h-screen">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-500" />
            </div>
        )
    }

    return (
        <div className="h-screen flex flex-col bg-background">
            <nav className="border-b px-4 py-3 flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <h1 className="text-xl font-bold">AI Webtoon Studio</h1>
                    <span className="text-sm text-muted-foreground">Chat Mode</span>
                    <ChatProjectPicker currentProjectId={projectId} />
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="ghost" size="sm" onClick={() => setConversationId(generateId())}>
                        新对话
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => router.push(`/agent/${projectId}/episodes`)}>
                        查看集数
                    </Button>
                </div>
            </nav>
            <ChatPanel
                conversationId={conversationId}
                projectId={projectId}
                className="flex-1"
            />
        </div>
    )
}
```

- [ ] **Step 2: Typecheck + smoke**

Visit `/chat/<a real project id>` — should load chat interface with project picker. Test 404 with bogus id.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/app/chat/[projectId]/page.tsx
git commit -m "feat(web): /chat/[projectId] route with project context + picker"
```

---

## Task 19: Studio topbar back-to-Agent link

**Files:** Modify `apps/web/src/components/studio/StudioTopbar.tsx`

- [ ] **Step 1: Read the current topbar**

Understand how `chapterId` and `projectId` are accessed (props vs store vs URL params).

- [ ] **Step 2: Read chapter source**

Add an effect that loads the chapter and reads `layout_json.source`:

```tsx
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Bot } from 'lucide-react'
import { chaptersApi } from '@/lib/api/services'

const router = useRouter()
const [sourceConversationId, setSourceConversationId] = useState<string | null>(null)

useEffect(() => {
    if (!chapterId) return
    chaptersApi.get(chapterId).then((ch: any) => {
        const src = ch?.layout_json?.source
        if (src?.type === 'agent' && src?.conversation_id) {
            setSourceConversationId(src.conversation_id)
        } else {
            setSourceConversationId(null)
        }
    }).catch(() => setSourceConversationId(null))
}, [chapterId])
```

(If `chaptersApi.get` doesn't exist, grep `services.ts` for how Studio currently loads the chapter — maybe `chapters.get` or via TanStack Query — and piggyback. Or read it from `studioStore` if already there.)

- [ ] **Step 3: Render link conditionally**

```tsx
{sourceConversationId && (
    <Button
        variant="ghost"
        size="sm"
        onClick={() => router.push(`/chat/${projectId}?conversation=${sourceConversationId}`)}
        className="gap-1"
    >
        <Bot className="w-4 h-4" />
        返回 Agent
    </Button>
)}
```

- [ ] **Step 4: Typecheck + smoke**

Verify button appears on an Agent-sourced chapter and hides on a manually-created one.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/studio/StudioTopbar.tsx
git commit -m "feat(web): Studio topbar back-to-Agent link"
```

---

## Task 20: AssetSourceBadge component

**Files:** Create `apps/web/src/components/assets/AssetSourceBadge.tsx`

- [ ] **Step 1: Write the component**

```tsx
'use client'

import { Bot } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import {
    Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from '@/components/ui/tooltip'

export interface AssetSourceBadgeProps {
    createdVia?: string | null
    sourceConversationId?: string | null
    size?: 'sm' | 'md'
}

export function AssetSourceBadge({ createdVia, sourceConversationId, size = 'md' }: AssetSourceBadgeProps) {
    if (createdVia !== 'agent') return null
    const sizeClass = size === 'sm' ? 'text-[10px] px-1.5 py-0.5' : 'text-xs px-2 py-0.5'

    return (
        <TooltipProvider delayDuration={150}>
            <Tooltip>
                <TooltipTrigger asChild>
                    <Badge variant="secondary" className={`inline-flex items-center gap-1 ${sizeClass}`}>
                        <Bot className="w-3 h-3" />
                        来自 Agent
                    </Badge>
                </TooltipTrigger>
                <TooltipContent>
                    {sourceConversationId
                        ? `由 Agent 对话 ${sourceConversationId.slice(0, 8)}… 创建`
                        : '由 Agent 对话创建'}
                </TooltipContent>
            </Tooltip>
        </TooltipProvider>
    )
}
```

- [ ] **Step 2: Typecheck + commit**

```bash
cd apps/web && npx tsc --noEmit
git add apps/web/src/components/assets/AssetSourceBadge.tsx
git commit -m "feat(web): AssetSourceBadge component"
```

---

## Task 21: Integrate AssetSourceBadge (BasicTab + AssetsTab + /assets)

**Files:** Modify 3 files.

- [ ] **Step 1: BasicTab**

In `apps/web/src/components/assets/drawer/BasicTab.tsx`, import and render:

```tsx
import { AssetSourceBadge } from '@/components/assets/AssetSourceBadge'

const createdVia = (asset as any).data_json?.created_via as string | undefined
const sourceConv = (asset as any).data_json?.source_conversation_id as string | undefined

// At top of returned JSX, before the first field:
<div className="flex items-center gap-2 pb-2 border-b border-white/10 mb-2">
    <span className="text-xs text-muted-foreground">来源</span>
    {createdVia === 'agent' ? (
        <AssetSourceBadge createdVia={createdVia} sourceConversationId={sourceConv} size="sm" />
    ) : (
        <span className="text-xs text-muted-foreground">手动创建</span>
    )}
</div>
```

- [ ] **Step 2: AssetsTab**

In `apps/web/src/components/studio/right/AssetsTab.tsx`, near asset rows/cards:

```tsx
import { AssetSourceBadge } from '@/components/assets/AssetSourceBadge'

// near the asset name:
<AssetSourceBadge
    createdVia={(asset as any).data_json?.created_via}
    sourceConversationId={(asset as any).data_json?.source_conversation_id}
    size="sm"
/>
```

- [ ] **Step 3: /assets page**

In `apps/web/src/app/assets/page.tsx` (or the `AssetCard` component if extracted), add the same badge to the card.

- [ ] **Step 4: Typecheck + smoke**

`cd apps/web && npx tsc --noEmit`. Visit `/assets` — agent-committed ones show the badge.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/assets/drawer/BasicTab.tsx \
        apps/web/src/components/studio/right/AssetsTab.tsx \
        apps/web/src/app/assets/page.tsx
git commit -m "feat(web): AssetSourceBadge in BasicTab/AssetsTab/assets"
```

(Include only files actually modified.)

---

## Task 22: End-to-end verification

**Files:** none

- [ ] **Step 1: Run all Cluster B1 backend tests**

```bash
cd D:/ai-webtoon-studio/apps/api && pytest \
    tests/unit/services/test_agent_spec_builder.py \
    tests/unit/services/test_agent_asset_sync.py \
    tests/unit/services/test_agent_idempotency.py \
    tests/unit/services/test_agent_conversation_reader.py \
    tests/unit/routes/test_agent_commit.py \
    -v 2>&1 | tail -40
```

Expected: all pass (roughly 6 + 4 + 4 + 4 + 6 = 24).

- [ ] **Step 2: Regression check on Cluster A**

```bash
cd D:/ai-webtoon-studio/apps/api && pytest \
    tests/unit/services/test_binding_service.py \
    tests/unit/routes/test_panel_bindings.py \
    tests/unit/routes/test_asset_usage.py -v 2>&1 | tail -10
```
Expect 21 pass.

- [ ] **Step 3: Frontend checks**

```bash
cd D:/ai-webtoon-studio/apps/web && npx tsc --noEmit 2>&1 | tail -5
cd D:/ai-webtoon-studio/apps/web && npm run lint 2>&1 | tail -20
```

- [ ] **Step 4: Manual Journey walkthrough**

Start infra + backend + celery + frontend, then:

- [ ] **Journey 1** — `/chat` landing → create project → `/chat/<pid>` → 对话生成大纲、角色、场景、某集 panels → `/agent/<pid>/episodes/1` detail → 点【在 Studio 打开】→ 跳到 Studio 画布，看到 panels 有预览图、右侧 AssetsTab 有角色/场景资产带 badge
- [ ] **Journey 2** — 在 episode 详情页再点一次【在 Studio 打开】→ toast "已打开已有章节"，DB 中 chapter 数量未增
- [ ] **Journey 3** — 项目切换器下拉切换项目 → URL 跳 `/chat/<new-pid>`
- [ ] **Journey 4** — Studio 顶栏显示【← 返回 Agent】链接，点击跳回对话
- [ ] **Journey 5** — 关闭 MinIO（或用 bogus URL 制造下载失败）→ commit 仍成功，toast "部分图片未能保存"
- [ ] **Journey 6** — 在 episodes 列表页点【一键提交全部到 Studio】→ 进度 "1/3 · 2/3 · 3/3" → 完成后对话历史里每一集都在 Studio 有对应 chapter

- [ ] **Step 5: Final commit log review**

```bash
git log --oneline | head -30
```

---

## Out of Scope

- **Studio → Agent reverse sync** — Studio edits don't propagate to conversation
- **Incremental commit** — re-committing after conversation edits is a no-op; requires B2 work
- **EpisodeTree component integration** — deferred to B2
- **Command-palette `Cmd+K`** — later
- **Chapter-level ACL beyond project-level** — deferred
- **WebSocket progress events during commit** — synchronous is sufficient for ≤10 images
- **Rich extraction beyond characters/scenes/panels/art_style cards** — if Agent adds new card types (timeline, dialogue, etc.) they won't transfer until `conversation_reader` is extended
