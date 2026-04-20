# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Webtoon Studio is a production platform for AI-generated webtoons (motion comics). The project is bilingual (Chinese docs, English code). It has **two main features** sharing a common asset library:

1. **Studio Workbench** — The core professional pipeline. A 4-panel workspace where users direct the full production flow: LLM-powered storyboard generation → human director refinement on a visual canvas (tweak camera/params, bind character portraits, select actions) → Payload Builder → ComfyUI GPU rendering → auto QA → timeline editing → export
2. **AI Agent (Chat-Driven)** — A more visual/conversational wrapper around the same pipeline. Users interact through chat to collaboratively refine scripts and storyboards with AI, making the director-storyboard process more interactive and accessible

Both features share the same **Asset Library** (characters with FaceID embeddings, scenes with anchors, props, styles) and the same backend services.

## Repository Structure

This is a two-app monorepo (no workspace manager — each app has independent dependencies):

- **`apps/web/`** — Next.js 14 frontend (TypeScript, Tailwind CSS, Radix UI, Konva canvas, Zustand state, TanStack Query)
- **`apps/api/`** — FastAPI backend (Python, SQLAlchemy, Alembic migrations, Celery workers, Pydantic schemas)
- **`docker/`** — Docker Compose for infrastructure (PostgreSQL, Redis, MinIO) and app containers

## Development Commands

### Infrastructure (Docker required)
```bash
cd docker && docker compose up -d postgres redis minio
```

### Backend API
```bash
cd apps/api
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Celery Worker (for async tasks: image gen, export, video)
```bash
cd apps/api
celery -A app.celery_app:celery_app worker --loglevel=info
```

### Frontend
```bash
cd apps/web
npm install
npm run dev          # runs on port 3001 (configured in package.json)
```

### Lint / Build
```bash
cd apps/web && npm run lint     # ESLint (next lint)
cd apps/web && npm run build    # Next.js production build
```

### Tests
```bash
cd apps/api
pytest                                          # all tests
pytest tests/unit/agents/test_schema_guard.py   # single test file
pytest -k test_name                             # single test by name
```

### One-click dev start (Windows)
```powershell
.\start-dev.ps1    # or start-dev.bat
```

## Two Main Features

### Studio Workbench (Core Pipeline)

The studio is the professional production tool — a 4-panel workspace for the full pipeline from script to export.

**Full pipeline flow:**
1. **Script input** → LLM Director Agent (analyzes script, breaks into storyboard, generates prompts) → Structured PanelSpec JSON list
2. **Human director operation** on the visual workbench canvas:
   - Modify camera angles / generation parameters
   - Select / replace character actions, bind skeleton action sequences
   - Drag character portraits to bind FaceID consistency assets
3. **Final storyboard commands** (Ready for Render) → Payload Builder & Router → ComfyUI node graph assembly → Redis/Celery task queue
4. **Render pipeline** on ComfyUI GPU cluster (see [ComfyUI Workflow](#comfyui-workflow-stages) below)
5. **Auto QA** (Vision LLM / scoring model) → Pass: save final clip → Timeline editing; Fail: retry logic (adjust seed / denoise strength)
6. **Export** → Strip PNG / motion MP4

**Frontend page:** `/projects/[projectId]/chapters/[chapterId]/studio`

**4-panel layout:**
- **Left:** `components/studio/left/ScriptEditor.tsx` — Script / asset list / ToFix queue
- **Center:** `components/canvas/StoryboardView.tsx` + `components/studio/center/CanvasStage.tsx` — Strip/Board + Panel Cards, Konva canvas for bubble dragging / layer adjustment / crop
- **Right:** `components/studio/right/InspectorTabs.tsx` — Story / Cast / Layout / Layers inspector
- **Bottom:** `components/studio/bottom/TimelineDock.tsx` + `components/studio/bottom/JobsConsole.tsx` — Timeline (Camera / Audio metadata) and render job monitoring

**State:** `lib/store/studioStore.ts` — Central state for panels, layers, jobs, timeline, viewer state

### AI Agent (Chat-Driven)

The agent provides a more visual, conversational version of the same pipeline. Users interact through chat to collaboratively refine scripts and storyboards with AI — making the director-storyboard process more interactive and accessible compared to the professional Studio Workbench.

**Frontend pages:**
- `/chat` — Conversational interface entry point
- `/studio/[projectId]` — Chat-driven studio with DirectorChat
- `/agent/[projectId]/episodes` — Agent workflow with episode management
- `/agent/[projectId]/episodes/[episodeNum]` — Individual episode detail

**Key components:**
- `components/chat/ChatPanel.tsx` — Main chat UI
- `components/studio/chat/DirectorChat.tsx` — Director-mode chat in studio
- `components/agent/AgentChat.tsx` — Agent conversation panel
- `components/agent/EpisodeTree.tsx` — Episode navigation tree
- `components/agent/PlanningPanel.tsx` — Planning/phase overview

**State:** `lib/store/chatStore.ts` — Conversation messages, agent status, streaming state

**Backend routes:** `api/routes/agent.py`, `api/routes/conversations.py`, `api/routes/orchestrator.py`

**Backend services:**
- `services/agents/` — Specialized agents: `director_agent`, `script_agent`, `asset_agent`, `rendering_agent`, `qa_agent` (all extend `base_agent`)
- `services/conversation/` — `intent_router` (classifies user messages), `agent_orchestrator` (coordinates agents), `tool_registry` + `tool_handlers` (agent tool system)
- `services/orchestrator/studio_orchestrator.py` — High-level pipeline orchestration

**Agent workflow phases:** Script Analysis → Storyboard Generation → Asset Creation → Render → QA/Fix → Export

## Shared Asset Library

Both features share a unified asset system. Assets are project-scoped and versioned.

**Asset types** (defined in `models/asset.py` `AssetType` enum):
- `character` — Characters with FaceID embeddings for consistency
- `scene` — Backgrounds with SceneAnchor + ControlNet maps
- `prop` — Props extracted from scripts
- `bubble` — Bubble/dialogue box styles
- `style` — StyleProfile (model stack + LoRA + prompt templates + sampler defaults)
- `effect` — Visual effects

**Consistency systems:**
- **Character consistency:** `FaceEmbedding` model + `services/identity/` (face extraction) + `services/faceid/` (IP-Adapter embedding) + `services/canonical/` (canonical reference generation) + `services/portrait/` (portrait generation with QA)
- **Scene consistency:** `SceneAnchor` model + `services/scene_anchor/` (anchor storage + control maps) + `services/scene/` (anchor generation + control map extraction)

**Supporting models:** `AssetVersion` (versioning), `AssetRelation` (inter-asset links), `OutfitVariant` (character outfit variants), `PropAsset`, `CharacterCanonical`

**Key routes:** `api/routes/assets.py`, `api/routes/identity.py`, `api/routes/faceid.py`, `api/routes/scene_anchor.py`, `api/routes/props.py`, `api/routes/asset_autobuild.py`

**Frontend page:** `/assets` — Asset management UI

## Backend Architecture

### System Layers

```
UI          Next.js + TS │ Studio Workbench (4-panel) │ Konva canvas │ WebSocket client
            ─────────────────────────────────────────────────────────────────────────
API         FastAPI │ Studio aggregate endpoint │ Storyboard Pipeline │ Consistency Checker
            Payload Builder │ Typesetter │ Exporter │ Jobs WebSocket Gateway
            ─────────────────────────────────────────────────────────────────────────
ENGINES     Generation engines (swappable providers):
            • LLM Provider (Mock → OpenAI / DeepSeek / Tongyi / Doubao)
            • FaceID Provider (Mock → InsightFace)
            • ComfyUI Cluster (Mock → real GPU nodes)
            • Vision QA (scoring model)
            ─────────────────────────────────────────────────────────────────────────
ASYNC       Redis → Celery Workers │ RenderJob status/logs
            ─────────────────────────────────────────────────────────────────────────
DATA        PostgreSQL │ MinIO/S3 │ VectorDB/pgvector (optional)
            ─────────────────────────────────────────────────────────────────────────
TOOLS       Playwright (SVG→PNG) │ OpenCV (compositing/parallax) │ FFmpeg (video export)
```

### Service Layer (`apps/api/app/services/`)

| Service | Purpose |
|---------|---------|
| `brain/` | LLM integration (script analysis → PanelSpec). Supports OpenAI, DeepSeek, Tongyi, Doubao via `LLM_PROVIDER`. Includes `storyboard_generator`, `name_resolver`, `repair/` loop |
| `layer_factory/` | ComfyUI workflow building + execution. `mock_comfyui.py` for dev without GPU. `workflow_builder.py` constructs workflow JSON. `prompt_compiler`, `render_planner`, `panel_renderer` |
| `identity/` | FaceID embedding extraction + storage |
| `scene_anchor/` | Background anchor + control map storage |
| `qa/` | Quality scoring (`image_qa`, `drift_detector`, `auto_retry`) → QAReport + FixPlan |
| `typesetter/` | SVG bubble placement + rendering |
| `composer/` | Strip composer (vertical scroll PNG) |
| `export/` | Release bundle builder, asset lock resolver, provenance collector, export gate |
| `storage/` | MinIO object store abstraction |
| `video/` | Video generation providers (Tongyi, Doubao, ComfyUI) |
| `agents/` | Agent system (director, script, asset, rendering, QA agents + schema guard) |
| `conversation/` | Chat system (intent router, agent orchestrator, tool registry) |
| `orchestrator/` | Studio orchestrator for pipeline coordination |
| `graph/` | Dependency graph + version management for assets |
| `asset_hub/` | Asset matching, locking, generation |
| `portrait/` | Character portrait generation with QA |
| `scene/` | Scene anchor + control map generation |
| `canonical/` | Canonical character reference management |
| `faceid/` | FaceID provider + embedder |

### ComfyUI Workflow Stages

Each panel render goes through a multi-stage ComfyUI node graph:

```
IN (Inputs)                          OUT (Package)
├─ Style profile                     ├─ Upload to S3
├─ PanelSpec JSON                    ├─ Write LayerPack meta
├─ FaceID embedding                  └─ WS push notification
├─ Scene BG anchor
├─ Control maps (lineart/depth/canny)
└─ Pose (optional)
        │
        ▼
R0  Full Render ─── Load model + Load LoRA + Text encode ±
                    + Apply FaceID + ControlNet (lineart/depth/canny/pose)
                    → Sampler → Decode → full.png
        │
        ▼
R1  Layer Cutout ── Segment → Refine mask → Cut alpha → char.png
        │
        ▼
R2  BG Inpaint ──── Hole mask → Inpaint → bg.png
        │
        ▼
R3  FG (Optional) ─ FX mask → FX gen → fg.png
        │
        ▼
       OUT
```

### Render Pipeline (Motion/Video)

For motion comic output, the GPU cluster runs 4 steps after the base image render:

1. **Step 1** — Generate / load consistency base image
2. **Step 2** — Apply skeleton / depth control
3. **Step 3** — SVD / AnimateDiff video frame generation
4. **Step 4** — Frame interpolation / super-resolution / lip sync

Then **Auto QA** (Vision LLM / scoring model):
- **Pass** → Save final video clip → Enter timeline editing
- **Fail** → Retry logic (adjust seed / denoise strength / boost FaceID weight)

### Celery Task Queues (`apps/api/app/workers/`)

Async tasks are routed to dedicated queues: `image`, `anchor`, `video`, `export`, `default`.

Workers: `image_worker`, `anchor_worker`, `video_worker`, `export_worker`, `advanced_worker`, `bundle_worker`.

### Data Flow Pipeline

1. Script → `brain/` → Chapter layout JSON + PanelSpec[]
2. PanelSpec → Payload Builder → `layer_factory/` → ComfyUI workflow JSON → RenderJob → LayerPack (full/char/bg/fg/mask PNGs + manifest)
3. LayerPack → `typesetter/` → text layer with bubbles
4. LayerPack → `composer/` → strip PNG or parallax motion MP4
5. Outputs → `qa/` → QAReport → FixPlan → auto-retry if needed
6. Final → `export/` → release bundle with provenance

### WebSocket Event System

Real-time updates via WebSocket (`api/routes/ws.py`). Frontend client: `lib/ws/client.ts` (dual-mode: real WS + mock fallback, toggled by `NEXT_PUBLIC_USE_REAL_WS`). Chat-specific client: `lib/ws/chatClient.ts`.

Event types (defined in `lib/ws/events.ts`):
- **Render:** `job_created`, `job_progress`, `job_status`, `panel_status`, `layerpack_ready`, `qa_result`
- **Video:** `video_job_created`, `video_job_progress`, `video_job_status`, `clip_status`, `clip_output_ready`
- **Export:** `export_job_created`, `export_job_progress`, `export_job_status`, `export_ready`
- **Storyboard:** `storyboard_progress`, `storyboard_done`, `storyboard_error`, `storyboard_draft_ready`

## Frontend Architecture (`apps/web/src/`)

- **State:** Two Zustand stores — `studioStore.ts` (studio workspace state) and `chatStore.ts` (conversation/agent state)
- **API layer:** `lib/api/client.ts` (fetch wrapper with auth), `lib/api/services.ts` (typed API calls), `lib/api/orchestrator.ts` (pipeline orchestration), `lib/api/endpoints.ts` (URL definitions)
- **WebSocket:** `lib/ws/client.ts` (dual-mode), `lib/ws/realWsClient.ts`, `lib/ws/chatClient.ts`, `lib/ws/events.ts`, `lib/ws/mockWsServer.ts`
- **Schemas:** `lib/schema/` — 33 Zod-validated TypeScript types mirroring backend models
- **Canvas:** Konva-based (`react-konva`) for bubble editing and panel preview
- **Pages:** Next.js App Router — `/dashboard`, `/projects`, `/assets`, `/production`, `/chat`, `/studio/[projectId]`, `/agent/[projectId]/episodes`, `/projects/[projectId]/chapters/[chapterId]/studio`

## Key Data Models (`apps/api/app/models/`)

**Core pipeline:** Project → Chapter → Panel → ShotVersion → RenderJob → RenderAttempt → LayerPack → Artifact

**Asset system:** Asset → AssetVersion, AssetRelation, FaceEmbedding, SceneAnchor, OutfitVariant, PropAsset, CharacterCanonical

**Quality & export:** QAReport, FixPlan, ExportJob, Export

**Conversation:** Conversation → ConversationMessage → ConversationAction

**Supporting:** Template, StoryboardDraft, Studio, Revision, Job, Timeline, Bindings

### Database Migrations

Alembic migrations in `apps/api/migrations/versions/`. Run `alembic upgrade head` after pulling. Create new migrations with `alembic revision --autogenerate -m "description"`.

## Ports

| Service | Port |
|---------|------|
| Frontend (Next.js) | 3001 |
| Backend (FastAPI) | 8000 |
| API docs (Swagger) | 8000/docs |
| PostgreSQL | 5432 |
| Redis | 6379 |
| MinIO API / Console | 9000 / 9001 |

## Environment Variables

Copy `.env.example` to `.env` at project root. Key variables:
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis for Celery broker/backend
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`
- `COMFYUI_URL` — leave empty to use mock renderer
- `LLM_PROVIDER` — one of: `openai`, `deepseek`, `tongyi`, `doubao`
- Provider-specific keys: `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `TONGYI_API_KEY`, `DOUBAO_API_KEY`
- `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`), `NEXT_PUBLIC_WS_BASE_URL`, `NEXT_PUBLIC_USE_REAL_WS`
- `ENABLE_AUTH` — JWT auth toggle (default true). Initial admin: `admin`/`admin`

## Domain Terminology

- **PanelSpec** — JSON specification for a single panel (characters, scene, camera, dialogue, generation params)
- **LayerPack** — Layered render output: full.png, char.png, bg.png, fg.png, mask.png + manifest.json
- **StyleProfile** — Model stack + LoRA + prompt templates + sampler defaults
- **SceneAnchor** — Background anchor image + control maps for scene consistency
- **FaceEmbedding** — IP-Adapter embedding for character face consistency across panels
- **CharacterCanonical** — Canonical reference image for a character
- **RenderAttempt** — Each execution of a RenderJob (tracks seed, workflow hash, outputs)
- **FixPlan** — Auto-retry strategy when QA fails (change seed, boost FaceID weight, inpaint, etc.)
- **StoryboardDraft** — AI-generated storyboard draft pending user review
- **ConversationAction** — Tool call or side-effect triggered by agent during chat
