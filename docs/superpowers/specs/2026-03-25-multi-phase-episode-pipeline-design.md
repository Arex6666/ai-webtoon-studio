# Multi-Phase Episode Pipeline Design

> **Date:** 2026-03-25
> **Status:** Approved
> **Scope:** Agent episode workflow — from script generation to video output

## Problem

The current Agent episode workflow calls a single API endpoint that tries to do everything at once: LLM script generation + panel image generation. This causes:

1. **Timeouts** — The LLM + 16 panel images takes >3 minutes, exceeding httpx/fetch timeouts
2. **No confirmation step** — Users can't review or refine characters/scenes before committing to panel rendering
3. **No iterative refinement** — Users can't adjust the output through conversation between phases
4. **Wasted GPU** — If one character is wrong, all panel images must be regenerated

## Solution

Replace the single-shot endpoint with a **4-phase pipeline** where each phase produces output the user can review and refine through conversation before proceeding.

```
Phase 1: Script + Character/Scene Images (automatic)
    ↓  user can refine via chat
Phase 2: User Confirms Assets (button click)
    ↓
Phase 3: Generate Panel First Frames (automatic)
    ↓  user can refine via chat
Phase 4: Generate Videos (button click → automatic)
```

## Architecture Overview

### Backend API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/episode/{n}/script` | POST | Generate script + character/scene images (refactored) |
| `/episode/{n}/generate-panels` | POST | Generate panel first frames (new) |
| `/episode/{n}/refine` | POST | LLM-driven refinement of any phase data (new) |
| `/episode/{n}/generate-video` | POST | Generate videos from first frames (existing) |

### Frontend State Machine

```
type EpisodePhase = 'loading' | 'script' | 'confirm' | 'panels' | 'video' | 'done'
```

---

## API Specifications

### Endpoint 1: `POST /api/v1/agent/episode/{episode_number}/script`

Refactored from the existing endpoint. Now generates only the script text + character images + scene images. Panel image generation is removed from this endpoint.

**Request:**

```json
{
  "project_id": "uuid",
  "episode_number": 2,
  "outline_text": "大纲内容...",
  "conversation_context": [{"role": "user", "content": "..."}]  // optional
}
```

**Response (`EpisodeScriptResponse`):**

```json
{
  "episode_number": 2,
  "episode_title": "第2集：深渊攀爬",
  "story_summary": "200-300字梗概...",
  "highlights": [
    {"title": "亮点标题", "description": "亮点描述"}
  ],
  "art_style": {
    "base_style": "韩漫二次元",
    "color_tone": "暗冷色调",
    "atmosphere": "紧张压抑"
  },
  "characters": [
    {
      "name": "阿澈",
      "description": "角色设定描述",
      "visual_prompt": "English visual descriptors for image generation",
      "image_url": "https://minio/.../char_uuid.jpg"
    }
  ],
  "scenes": [
    {
      "name": "星渊崖壁",
      "description": "场景描述",
      "visual_prompt": "English scene descriptors",
      "image_url": "https://minio/.../scene_uuid.jpg"
    }
  ],
  "panels": [
    {
      "id": "02-1",
      "scene_name": "星渊崖壁",
      "scene_description": "画面描述",
      "composition": "全景俯拍",
      "camera_movement": "缓慢下推",
      "characters": ["阿澈"],
      "voice_character": "旁白",
      "dialogue": "台词内容",
      "duration_sec": 5
    }
  ]
}
```

**Key changes from current:**
- Character images: generated using portrait-style prompt (`"{visual_prompt}, character portrait, upper body, anime style"`)
- Scene images: generated using landscape prompt (`"{visual_prompt}, wide shot, background art, no characters"`)
- Panel `image_url` field removed — panels have no images at this stage
- Panel `duration_sec` added — LLM specifies 3-10 seconds per panel
- Image generation concurrency: semaphore=5 (characters + scenes in parallel)
- Expected response time: ~30-60 seconds

### Endpoint 2: `POST /api/v1/agent/episode/{episode_number}/generate-panels`

New endpoint. Takes confirmed character/scene data and generates a first-frame image for each panel.

**Request:**

```json
{
  "project_id": "uuid",
  "art_style": {
    "base_style": "韩漫二次元",
    "color_tone": "暗冷色调",
    "atmosphere": "紧张压抑"
  },
  "characters": [
    {"name": "阿澈", "visual_prompt": "...", "image_url": "https://..."}
  ],
  "scenes": [
    {"name": "星渊崖壁", "visual_prompt": "...", "image_url": "https://..."}
  ],
  "panels": [
    {
      "id": "02-1",
      "scene_name": "星渊崖壁",
      "scene_description": "画面描述",
      "composition": "全景俯拍",
      "characters": ["阿澈"]
    }
  ]
}
```

**Response:**

```json
{
  "panels": [
    {"id": "02-1", "image_url": "https://minio/.../panel_02-1.jpg", "status": "success"},
    {"id": "02-2", "image_url": null, "status": "failed", "error": "generation timeout"}
  ]
}
```

**Implementation:**
- For each panel, compose a prompt from: art_style + scene visual_prompt + character visual_prompts + scene_description + composition
- Same logic as current panel image generation in `agent.py` lines 625-679
- Concurrency: semaphore=5
- Failed panels return `status: "failed"` — frontend can retry individual panels

### Endpoint 3: `POST /api/v1/agent/episode/{episode_number}/refine`

New endpoint. Accepts a user's natural language instruction and uses LLM to determine what changes to make to the current script data.

**Request:**

```json
{
  "phase": "confirm",
  "message": "把阿澈的发色改成银色",
  "current_data": {
    "art_style": {...},
    "characters": [...],
    "scenes": [...],
    "panels": [...]
  }
}
```

**Response:**

```json
{
  "action": "update_character",
  "updates": {
    "characters": [
      {
        "name": "阿澈",
        "description": "更新后的角色描述",
        "visual_prompt": "updated English descriptors with silver hair",
        "regenerate_image": true
      }
    ]
  },
  "affected_panels": ["02-1", "02-3", "02-7"],
  "reply": "好的，已把阿澈的发色改成银色。正在重新生成角色图..."
}
```

**Supported actions:**

| action | Description |
|--------|-------------|
| `update_character` | Modify character description/visual_prompt |
| `update_scene` | Modify scene description/visual_prompt |
| `add_scene` | Add a new scene |
| `remove_scene` | Remove a scene |
| `update_panel` | Modify panel composition/description/dialogue |
| `update_art_style` | Modify overall art style |
| `reorder_panels` | Change panel order |
| `add_panel` | Insert a new panel |
| `remove_panel` | Remove a panel |
| `chat` | General conversation (no data changes) |

**LLM system prompt** instructs the model to:
1. Parse user intent against the current data
2. Return structured JSON with only the changed fields
3. Set `regenerate_image: true` on items that need re-rendering
4. List `affected_panels` (panels containing modified characters/scenes)

**After receiving the response, the frontend:**
1. Merges `updates` into local `script_data`
2. If `regenerate_image: true`, calls DoubaoImageProvider for affected items
3. Displays the LLM's `reply` as a chat message
4. If in `panels` phase, regenerates affected panel first frames
5. If in `video` phase, marks affected videos for re-generation

### Endpoint 4: `POST /api/v1/agent/episode/{episode_number}/generate-video`

Existing endpoint, unchanged. Frontend now sends `duration_sec` from panel data instead of user manual input.

---

## Frontend Design

### Phase State Machine

```typescript
type EpisodePhase = 'loading' | 'script' | 'confirm' | 'panels' | 'video' | 'done'

// State stored in component
interface EpisodePipelineState {
  phase: EpisodePhase
  scriptData: EpisodeScriptData | null   // from Phase 1
  panelImages: Record<string, string>     // panel_id → image_url, from Phase 3
  videoJobs: VideoJobState[]              // from Phase 4
}
```

### Phase Transitions

```
loading ──(load history)──→ restore to saved phase
loading ──(no history)───→ script

script  ──(API success)──→ confirm
script  ──(API failure)──→ script (show error + retry)

confirm ──(user clicks confirm)──→ panels
confirm ──(user sends message)──→ confirm (refine, stay in phase)

panels  ──(all images done)──→ video
panels  ──(partial failure)──→ panels (show retry for failed)
panels  ──(user sends message)──→ panels (refine + regenerate affected)

video   ──(all videos done)──→ done
video   ──(user sends message)──→ video (refine + regenerate affected)

done    ──(user sends message)──→ done (compose or refine)
```

### UI Layout Per Phase

#### Phase: `confirm`

After script markdown is displayed:

```
┌─────────────────────────────────────────────┐
│  [Chat messages with script markdown]        │
│  - Episode title, summary, highlights        │
│  - Art style table                           │
│  - Characters with generated portraits       │
│  - Scenes with generated landscape images    │
│  - Panels list (text only, no images)        │
│                                              │
│  Chat input: "把阿澈的衣服改成蓝色..."       │
├─────────────────────────────────────────────┤
│  [✓ 确认角色与场景，开始生成分镜首帧]          │  ← action bar
└─────────────────────────────────────────────┘
```

#### Phase: `panels`

```
┌─────────────────────────────────────────────┐
│  [Previous messages]                         │
│                                              │
│  正在生成分镜首帧...                          │
│  ████████░░░░░░░░  8/16                      │  ← progress bar
│                                              │
│  [Grid of panel thumbnails]                  │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐       │
│  │ 02-1 │ │ 02-2 │ │ 02-3 │ │ 02-4 │       │
│  │ ✓    │ │ ✓    │ │ ...  │ │ ░░░  │       │
│  └──────┘ └──────┘ └──────┘ └──────┘       │
│                                              │
│  Chat input: "03-5的构图改成特写..."          │
├─────────────────────────────────────────────┤
│  [⏳ 等待分镜生成完成...]                      │
│  or                                          │
│  [▶ 生成全部视频]                             │  ← after all panels done
└─────────────────────────────────────────────┘
```

#### Phase: `video`

```
┌─────────────────────────────────────────────┐
│  [Previous messages]                         │
│                                              │
│  VideoCard component (existing, enhanced):   │
│  - Pre-filled duration_sec from panel data   │
│  - Pre-filled motion_prompt from panel data  │
│  - Progress bars per video                   │
│  - Play buttons for completed videos         │
│                                              │
│  Chat input: "第3个视频运动太快..."            │
├─────────────────────────────────────────────┤
│  [🎬 合成视频]                               │  ← after all videos done
└─────────────────────────────────────────────┘
```

### Message Handling by Phase

When user sends a message, the handler checks `phase`:

```typescript
const handleSendMessage = async (content: string) => {
  // Save user message
  ...

  if (phase === 'confirm' || phase === 'panels' || phase === 'video') {
    // Route to refine endpoint
    const result = await refineEpisode(episodeNum, phase, content, scriptData)

    // Display LLM reply
    addMessage('assistant', result.reply)

    // Apply updates to local state
    if (result.updates) {
      mergeUpdates(result.updates)

      // Regenerate affected images
      if (result.updates.characters?.some(c => c.regenerate_image)) {
        await regenerateCharacterImages(result.updates.characters)
      }
      if (result.updates.scenes?.some(s => s.regenerate_image)) {
        await regenerateSceneImages(result.updates.scenes)
      }
      if (phase === 'panels' && result.affected_panels?.length) {
        await regeneratePanelImages(result.affected_panels)
      }
    }
  } else {
    // Default chat handling (video intent detection, etc.)
    ...
  }
}
```

---

## Data Persistence

### Conversation Message Storage

Pipeline state is persisted via `entities_json` on conversation messages, enabling page refresh recovery.

```typescript
// After Phase 1 (script) completes:
saveMessage('assistant', scriptMarkdown, {
  type: 'episode_pipeline',
  phase: 'confirm',
  script_data: { episode_title, story_summary, highlights, art_style, characters, scenes, panels }
})

// After Phase 3 (panels) completes:
saveMessage('assistant', panelResultMarkdown, {
  type: 'episode_pipeline',
  phase: 'video',
  script_data: { ... },
  panel_images: { "02-1": "https://...", "02-2": "https://...", ... }
})

// After Phase 4 (video) completes:
saveMessage('assistant', videoResultMarkdown, {
  type: 'episode_pipeline',
  phase: 'done',
  script_data: { ... },
  panel_images: { ... },
  video_jobs: [{ panel_id: "02-1", job_id: "uuid", video_url: "https://..." }]
})
```

### Page Load Recovery

```typescript
// On page load:
const pipelineMsg = historyMessages.findLast(m =>
  m.card?.type === 'episode_pipeline'
)

if (pipelineMsg) {
  // Restore state from saved data
  setPhase(pipelineMsg.card.phase)
  setScriptData(pipelineMsg.card.script_data)
  setPanelImages(pipelineMsg.card.panel_images || {})
  setVideoJobs(pipelineMsg.card.video_jobs || [])
} else {
  // Fresh start
  setPhase('script')
  triggerScriptGeneration()
}
```

### Refine Updates

When a refine operation modifies data, a new message is saved with the updated `script_data`. The recovery logic always uses the **last** `episode_pipeline` message, so it naturally picks up refinements.

---

## Error Handling

| Failure Point | Recovery |
|---------------|----------|
| Script generation timeout/error | Show error message + retry button in action bar |
| Character/scene image partial failure | Show placeholder for failed images, enter `confirm` phase normally. User can request regeneration via chat: "重新生成阿澈的角色图" |
| Panel first frame partial failure | Show failed panels with retry icon. "重试失败项" button retries only failed panels |
| Refine endpoint failure | Show error in chat, user can retry by sending the message again |
| Video generation failure | Existing VideoCard retry logic (per-job retry) |
| Page refresh during generation | Restore to last completed phase. In-progress generation is lost but can be re-triggered |

---

## Files to Modify

### Backend (apps/api/)

| File | Change |
|------|--------|
| `app/api/routes/agent.py` | Refactor `generate_full_episode_script`: remove panel image gen, add character/scene image gen, add `duration_sec` to panel schema. Add `generate_panels` endpoint. Add `refine` endpoint. |
| `app/services/brain/standard_llm.py` | Timeout already increased to 180s (done) |

### Frontend (apps/web/src/)

| File | Change |
|------|--------|
| `app/agent/[projectId]/episodes/[episodeNum]/page.tsx` | Major rewrite: implement phase state machine, refine message routing, panel generation UI, phase persistence/recovery |
| `components/agent/AgentChat.tsx` | No changes needed (customContent already supports action buttons) |
| `components/agent/VideoCard.tsx` | Minor: accept pre-filled `duration_sec` and `motion_prompt` from panel data |
| `lib/api/types.ts` | Add `EpisodeScriptData`, `PanelGenerateRequest/Response`, `RefineRequest/Response` types |

### New Files

| File | Purpose |
|------|---------|
| `lib/api/episodeApi.ts` | API client functions for the 3 episode endpoints |

---

## Out of Scope

- Character/scene editing UI (drag-and-drop, crop, etc.) — users refine via chat only
- Real-time WebSocket progress for panel/video generation — polling is sufficient
- Multi-episode consistency (shared character assets across episodes) — future work
- Undo/redo for refinements — conversation history serves as implicit undo log
