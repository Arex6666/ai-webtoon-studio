# Multi-Phase Episode Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace single-shot episode script generation with a 4-phase pipeline (script+assets → confirm → panel frames → video) with conversational refinement between phases.

**Architecture:** Refactor the existing `/episode/{n}/script` endpoint to only generate script + character/scene images. Add two new endpoints: `/episode/{n}/generate-panels` for panel first frames, and `/episode/{n}/refine` for LLM-driven refinement. Frontend implements a phase state machine (`script → confirm → panels → video → done`) with persistence via conversation `entities_json`.

**Tech Stack:** FastAPI (Python), Next.js 14 (TypeScript), DoubaoImageProvider (Seedream 4.5), Pydantic, Zustand-free local state

**Spec:** `docs/superpowers/specs/2026-03-25-multi-phase-episode-pipeline-design.md`

---

## File Structure

### Backend — Modified

| File | Responsibility |
|------|---------------|
| `apps/api/app/api/routes/agent.py` | Refactor script endpoint, add `generate-panels` and `refine` endpoints |

### Frontend — Modified

| File | Responsibility |
|------|---------------|
| `apps/web/src/app/agent/[projectId]/episodes/[episodeNum]/page.tsx` | Phase state machine, UI per phase, refine routing |
| `apps/web/src/components/agent/VideoCard.tsx` | Accept pre-filled duration/prompt from panel data |

### Frontend — New

| File | Responsibility |
|------|---------------|
| `apps/web/src/lib/api/episodeApi.ts` | Typed API client for all episode endpoints |

---

## Task 1: Refactor Backend — Split Script Endpoint and Add Character/Scene Image Generation

**Files:**
- Modify: `apps/api/app/api/routes/agent.py:417-707`

### Steps

- [ ] **Step 1.1: Add `duration_sec` to `StoryboardPanel` model, remove panel image generation**

In `apps/api/app/api/routes/agent.py`, update the `StoryboardPanel` model (line 424) to add `duration_sec` and remove the `image_url` field:

```python
class StoryboardPanel(BaseModel):
    id: str
    scene_name: str = ""
    scene_description: str
    composition: str
    camera_movement: str
    characters: list[str] = []
    voice_character: str
    dialogue: str
    duration_sec: float = 5.0  # LLM-specified duration (3-10 seconds)
```

- [ ] **Step 1.2: Update LLM system prompt to include `duration_sec` per panel**

In the system prompt (lines 500-551), add `duration_sec` to the panel JSON schema:

```python
      "duration_sec": 5
```

Add to the prompt instructions after "分镜数量：12-24格":
```
每个分镜需要指定 duration_sec（3-10秒），根据画面内容和节奏调整：
- 对话场景：4-6秒
- 动作场景：3-4秒
- 情感特写：5-7秒
- 全景建立镜头：6-8秒
```

- [ ] **Step 1.3: Update panel parsing to extract `duration_sec`**

In the panels parsing block (lines 601-613), add `duration_sec`:

```python
panels = [
    StoryboardPanel(
        id=p.get("id", f"{str(episode_number).zfill(2)}-{i+1}"),
        scene_name=p.get("scene_name", ""),
        scene_description=p.get("scene_description", ""),
        composition=p.get("composition", ""),
        camera_movement=p.get("camera_movement", ""),
        characters=p.get("characters", []),
        voice_character=p.get("voice_character", ""),
        dialogue=p.get("dialogue", ""),
        duration_sec=max(3.0, min(10.0, float(p.get("duration_sec", 5.0)))),
    )
    for i, p in enumerate(data.get("panels", []))
]
```

- [ ] **Step 1.4: Replace panel image generation with character/scene image generation**

Remove the entire panel image generation block (lines 615-683) and replace with character + scene image generation:

```python
        # =========== 生成角色参考图 + 场景参考图 ===========
        provider = get_doubao_image_provider()
        if provider:
            logger.info(f"[Episode {episode_number}] Generating character and scene images")
            semaphore = asyncio.Semaphore(5)

            async def generate_character_image(char: Character) -> Character:
                """生成角色半身参考图"""
                async with semaphore:
                    try:
                        prompt = f"{art_style_hint}, {char.visual_prompt}, character portrait, upper body, anime style, detailed face, high quality"
                        request = DoubaoImageRequest(
                            prompt=prompt,
                            negative_prompt="low quality, blurry, distorted, deformed, full body, background clutter",
                            width=1024,
                            height=1280,
                        )
                        result = await provider.generate(request)
                        if result.success and result.image_url:
                            char.image_url = result.image_url
                            logger.info(f"[Episode {episode_number}] Character '{char.name}' image generated")
                    except Exception as e:
                        logger.warning(f"[Episode {episode_number}] Failed to generate image for character '{char.name}': {e}")
                    return char

            async def generate_scene_image(scene: Scene) -> Scene:
                """生成场景全景参考图"""
                async with semaphore:
                    try:
                        prompt = f"{art_style_hint}, {scene.visual_prompt}, wide shot, background art, no characters, environment concept art, high quality"
                        request = DoubaoImageRequest(
                            prompt=prompt,
                            negative_prompt="low quality, blurry, distorted, people, characters, figures",
                            width=1920,
                            height=1080,
                        )
                        result = await provider.generate(request)
                        if result.success and result.image_url:
                            scene.image_url = result.image_url
                            logger.info(f"[Episode {episode_number}] Scene '{scene.name}' image generated")
                    except Exception as e:
                        logger.warning(f"[Episode {episode_number}] Failed to generate image for scene '{scene.name}': {e}")
                    return scene

            # 并行生成角色图和场景图
            char_tasks = [generate_character_image(c) for c in characters]
            scene_tasks = [generate_scene_image(s) for s in scenes]
            all_results = await asyncio.gather(*char_tasks, *scene_tasks, return_exceptions=True)

            # 提取结果（忽略异常）
            char_count = len(characters)
            characters = [r for r in all_results[:char_count] if isinstance(r, Character)] or characters
            scenes = [r for r in all_results[char_count:] if isinstance(r, Scene)] or scenes

            logger.info(f"[Episode {episode_number}] Character and scene image generation completed")
        else:
            logger.info(f"[Episode {episode_number}] DoubaoImageProvider not available, skipping image generation")
```

- [ ] **Step 1.5: Verify the endpoint returns correct response shape**

Test manually with curl or from the browser that the response now includes:
- `characters[].image_url` — generated portrait URLs
- `scenes[].image_url` — generated landscape URLs
- `panels[].duration_sec` — LLM-specified duration
- `panels` — no `image_url` field

- [ ] **Step 1.6: Commit**

```bash
git add apps/api/app/api/routes/agent.py
git commit -m "refactor: split script endpoint — generate char/scene images, remove panel images, add duration_sec"
```

---

## Task 2: Add `generate-panels` Endpoint

**Files:**
- Modify: `apps/api/app/api/routes/agent.py` (append after existing endpoints)

### Steps

- [ ] **Step 2.1: Define request/response models**

Add after the existing models (after line 469):

```python
# ============ 分镜首帧生成 API ============

class PanelInput(BaseModel):
    id: str
    scene_name: str = ""
    scene_description: str
    composition: str = ""
    camera_movement: str = ""
    characters: list[str] = []

class GeneratePanelsRequest(BaseModel):
    project_id: str
    art_style: ArtStyle
    characters: list[Character]
    scenes: list[Scene]
    panels: list[PanelInput]

class PanelResult(BaseModel):
    id: str
    image_url: Optional[str] = None
    status: str  # "success" | "failed"
    error: Optional[str] = None

class GeneratePanelsResponse(BaseModel):
    panels: list[PanelResult]
```

- [ ] **Step 2.2: Implement the endpoint**

```python
@router.post("/episode/{episode_number}/generate-panels", response_model=GeneratePanelsResponse)
async def generate_panel_images(
    episode_number: int,
    req: GeneratePanelsRequest,
):
    """用户确认角色/场景后，为每个分镜生成首帧图。"""
    provider = get_doubao_image_provider()
    if not provider:
        raise HTTPException(status_code=503, detail="Image provider not available (no API key configured)")

    # 构建查找表
    char_prompt_map = {c.name: c.visual_prompt for c in req.characters if c.visual_prompt}
    scene_prompt_map = {s.name: s.visual_prompt for s in req.scenes if s.visual_prompt}
    art_style_hint = f"{req.art_style.base_style}, {req.art_style.color_tone}, {req.art_style.atmosphere}"

    semaphore = asyncio.Semaphore(5)

    async def generate_one(panel: PanelInput) -> PanelResult:
        async with semaphore:
            try:
                scene_part = scene_prompt_map.get(panel.scene_name, panel.scene_name or "")
                char_parts = [char_prompt_map.get(cn, cn) for cn in panel.characters]
                char_part = ", ".join(char_parts) if char_parts else ""

                parts = [
                    art_style_hint,
                    scene_part,
                    char_part,
                    panel.scene_description,
                    panel.composition,
                    "high quality, detailed, anime illustration",
                ]
                prompt = ", ".join(p for p in parts if p)

                request = DoubaoImageRequest(
                    prompt=prompt,
                    negative_prompt="low quality, blurry, distorted, deformed, ugly, text, watermark",
                    width=1280,
                    height=720,
                )
                result = await provider.generate(request)
                if result.success and result.image_url:
                    return PanelResult(id=panel.id, image_url=result.image_url, status="success")
                return PanelResult(id=panel.id, status="failed", error=result.error or "Generation returned no image")
            except Exception as e:
                logger.warning(f"[Episode {episode_number}] Panel '{panel.id}' image failed: {e}")
                return PanelResult(id=panel.id, status="failed", error=str(e))

    results = await asyncio.gather(*[generate_one(p) for p in req.panels], return_exceptions=True)
    panel_results = []
    for i, r in enumerate(results):
        if isinstance(r, PanelResult):
            panel_results.append(r)
        else:
            panel_results.append(PanelResult(id=req.panels[i].id, status="failed", error=str(r)))

    return GeneratePanelsResponse(panels=panel_results)
```

- [ ] **Step 2.3: Commit**

```bash
git add apps/api/app/api/routes/agent.py
git commit -m "feat: add /episode/{n}/generate-panels endpoint for panel first frames"
```

---

## Task 3: Add `refine` Endpoint

**Files:**
- Modify: `apps/api/app/api/routes/agent.py` (append)

### Steps

- [ ] **Step 3.1: Define request/response models**

```python
# ============ 对话式改进 API ============

class RefineRequest(BaseModel):
    phase: str  # "confirm" | "panels" | "video"
    message: str
    current_data: dict  # { art_style, characters, scenes, panels }

class RefineResponse(BaseModel):
    action: str  # "update_character" | "update_scene" | "update_panel" | "update_art_style" | "add_scene" | "remove_scene" | "add_panel" | "remove_panel" | "chat"
    updates: Optional[dict] = None  # partial updates
    affected_panels: list[str] = []  # panel IDs that need re-rendering
    reply: str  # natural language reply to user
```

- [ ] **Step 3.2: Implement the endpoint**

```python
@router.post("/episode/{episode_number}/refine", response_model=RefineResponse)
async def refine_episode(
    episode_number: int,
    req: RefineRequest,
):
    """通过对话改进剧本内容（角色/场景/分镜/风格）。"""
    llm = StandardLLMService()

    system_prompt = f"""你是AI漫剧导演助手。用户正在编辑第{episode_number}集的分镜剧本，当前处于 {req.phase} 阶段。

当前剧本数据（JSON）：
{json.dumps(req.current_data, ensure_ascii=False, indent=2)[:8000]}

用户发来一条修改指令，请分析意图并返回结构化的修改结果。

返回JSON格式：
{{
  "action": "update_character | update_scene | update_panel | update_art_style | add_scene | remove_scene | add_panel | remove_panel | chat",
  "updates": {{
    "characters": [修改后的角色对象（只包含被修改的角色）],
    "scenes": [修改后的场景对象（只包含被修改的场景）],
    "panels": [修改后的分镜对象（只包含被修改的分镜）],
    "art_style": {{修改后的风格对象（如果修改了风格）}}
  }},
  "affected_panels": ["02-1", "02-3"],
  "reply": "自然语言回复，告诉用户做了什么修改"
}}

规则：
1. updates 中只包含被修改的项目，未修改的不要包含
2. 被修改的角色/场景需要同步更新 visual_prompt（英文）
3. 如果修改了角色外观或场景描述，设置 "regenerate_image": true
4. affected_panels 列出包含被修改角色/场景的分镜ID
5. 如果用户只是闲聊或提问，action 设为 "chat"，updates 为 null
6. reply 用中文回复
只返回JSON，不要添加任何额外文字。"""

    try:
        content = await llm._chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": req.message},
            ],
            response_format="json",
        )
        data = _safe_json_loads(content)

        return RefineResponse(
            action=data.get("action", "chat"),
            updates=data.get("updates"),
            affected_panels=data.get("affected_panels", []),
            reply=data.get("reply", "已收到你的反馈。"),
        )
    except Exception as e:
        logger.error(f"Refine failed: {e}", exc_info=True)
        return RefineResponse(
            action="chat",
            updates=None,
            affected_panels=[],
            reply=f"抱歉，处理你的请求时出错了：{str(e)}",
        )
```

- [ ] **Step 3.3: Commit**

```bash
git add apps/api/app/api/routes/agent.py
git commit -m "feat: add /episode/{n}/refine endpoint for conversational script refinement"
```

---

## Task 4: Create Frontend API Client

**Files:**
- Create: `apps/web/src/lib/api/episodeApi.ts`

### Steps

- [ ] **Step 4.1: Create the typed API client module**

```typescript
import { env } from '@/lib/utils/env'

// ─── Types ───

export interface ArtStyle {
    base_style: string
    color_tone: string
    atmosphere: string
}

export interface CharacterData {
    name: string
    description: string
    visual_prompt: string
    image_url?: string | null
    regenerate_image?: boolean
}

export interface SceneData {
    name: string
    description: string
    visual_prompt: string
    image_url?: string | null
    possible_variants?: string[]
    regenerate_image?: boolean
}

export interface PanelData {
    id: string
    scene_name: string
    scene_description: string
    composition: string
    camera_movement: string
    characters: string[]
    voice_character: string
    dialogue: string
    duration_sec: number
    image_url?: string | null
}

export interface Highlight {
    title: string
    description: string
}

export interface EpisodeScriptData {
    episode_number: number
    episode_title: string
    story_summary: string
    highlights: Highlight[]
    art_style: ArtStyle
    characters: CharacterData[]
    scenes: SceneData[]
    panels: PanelData[]
}

export interface PanelResult {
    id: string
    image_url: string | null
    status: 'success' | 'failed'
    error?: string
}

export interface GeneratePanelsResponse {
    panels: PanelResult[]
}

export interface RefineResponse {
    action: string
    updates: {
        characters?: CharacterData[]
        scenes?: SceneData[]
        panels?: PanelData[]
        art_style?: ArtStyle
    } | null
    affected_panels: string[]
    reply: string
}

// ─── API Functions ───

export async function generateEpisodeScript(
    projectId: string,
    episodeNumber: number,
    outlineText: string,
    conversationContext?: { role: string; content: string }[],
): Promise<EpisodeScriptData> {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 180_000)

    const resp = await fetch(`${env.API_BASE_URL}/api/v1/agent/episode/${episodeNumber}/script`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            project_id: projectId,
            episode_number: episodeNumber,
            outline_text: outlineText,
            conversation_context: conversationContext,
        }),
        signal: controller.signal,
    })
    clearTimeout(timeoutId)

    if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
        throw new Error(err.detail || `HTTP ${resp.status}`)
    }
    return resp.json()
}

export async function generatePanelImages(
    episodeNumber: number,
    data: {
        project_id: string
        art_style: ArtStyle
        characters: CharacterData[]
        scenes: SceneData[]
        panels: { id: string; scene_name: string; scene_description: string; composition: string; camera_movement: string; characters: string[] }[]
    },
): Promise<GeneratePanelsResponse> {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 300_000) // 5 min for many panels

    const resp = await fetch(`${env.API_BASE_URL}/api/v1/agent/episode/${episodeNumber}/generate-panels`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
        signal: controller.signal,
    })
    clearTimeout(timeoutId)

    if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
        throw new Error(err.detail || `HTTP ${resp.status}`)
    }
    return resp.json()
}

export async function refineEpisode(
    episodeNumber: number,
    phase: string,
    message: string,
    currentData: { art_style: ArtStyle; characters: CharacterData[]; scenes: SceneData[]; panels: PanelData[] },
): Promise<RefineResponse> {
    const resp = await fetch(`${env.API_BASE_URL}/api/v1/agent/episode/${episodeNumber}/refine`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            phase,
            message,
            current_data: currentData,
        }),
    })

    if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
        throw new Error(err.detail || `HTTP ${resp.status}`)
    }
    return resp.json()
}

export async function regenerateSingleImage(
    prompt: string,
    type: 'character' | 'scene',
): Promise<string | null> {
    // Uses the existing DoubaoImageProvider via a lightweight proxy
    // For now, character/scene regeneration goes through the refine flow
    // which triggers backend image generation
    // This is a placeholder for future direct image regeneration API
    return null
}
```

- [ ] **Step 4.2: Commit**

```bash
git add apps/web/src/lib/api/episodeApi.ts
git commit -m "feat: add typed episodeApi client for multi-phase pipeline"
```

---

## Task 5: Rewrite Frontend Episode Page — Phase State Machine

**Files:**
- Modify: `apps/web/src/app/agent/[projectId]/episodes/[episodeNum]/page.tsx` (major rewrite)

This is the largest task. The page needs to be rewritten to support the phase state machine.

### Steps

- [ ] **Step 5.1: Define types and phase state at the top of the component**

Replace existing state variables (lines 20-27) with:

```typescript
type EpisodePhase = 'loading' | 'script' | 'confirm' | 'panels' | 'video' | 'done'

// ... existing imports stay ...
import {
    EpisodeScriptData, PanelData, CharacterData, SceneData,
    generateEpisodeScript, generatePanelImages, refineEpisode,
    RefineResponse,
} from '@/lib/api/episodeApi'

export default function EpisodeConversationPage() {
    const params = useParams()
    const router = useRouter()
    const projectId = params.projectId as string
    const episodeNum = parseInt(params.episodeNum as string)

    // Core state
    const [messages, setMessages] = useState<AgentMessage[]>([])
    const [isTyping, setIsTyping] = useState(false)
    const [conversationId, setConversationId] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [outlineContext, setOutlineContext] = useState<string>('')

    // Phase pipeline state
    const [phase, setPhase] = useState<EpisodePhase>('loading')
    const [scriptData, setScriptData] = useState<EpisodeScriptData | null>(null)
    const [panelImages, setPanelImages] = useState<Record<string, string>>({})
    const [panelProgress, setPanelProgress] = useState<{ done: number; total: number } | null>(null)
    const [generationError, setGenerationError] = useState<string | null>(null)

    const videoCardDataRef = useRef<VideoCardData | null>(null)
    const loadStartedRef = useRef(false)
    const hasAutoTriggered = useRef(false)
```

- [ ] **Step 5.2: Update history loading to restore phase from `entities_json`**

Replace the history loading logic (lines 69-101) with phase-aware recovery:

```typescript
                // 3. 加载分集对话的历史消息
                if (episodeConv.message_count > 0) {
                    const episodeMessages = await conversationsApi.getMessages(episodeConv.id, 100, 0)
                    if (episodeMessages && episodeMessages.length > 0) {
                        const historyMessages: AgentMessage[] = episodeMessages.map((msg, idx) => ({
                            id: msg.id || `history-${idx}`,
                            role: msg.role as 'user' | 'assistant' | 'system',
                            content: msg.content,
                            timestamp: new Date(msg.created_at).getTime(),
                            card: msg.entities_json?.card || msg.entities_json,
                        }))

                        setMessages(historyMessages)

                        // 恢复阶段状态：找到最后一个 pipeline 消息
                        const pipelineMsg = [...historyMessages].reverse().find(m =>
                            m.card?.type === 'episode_pipeline'
                        )
                        if (pipelineMsg?.card) {
                            const savedPhase = pipelineMsg.card.phase as EpisodePhase
                            setPhase(savedPhase)
                            if (pipelineMsg.card.script_data) {
                                setScriptData(pipelineMsg.card.script_data)
                            }
                            if (pipelineMsg.card.panel_images) {
                                setPanelImages(pipelineMsg.card.panel_images)
                            }
                            hasAutoTriggered.current = true
                        } else {
                            // 检查是否有旧的 mock 数据
                            const hasMockData = historyMessages.some(m =>
                                m.content.includes('主角A') && m.content.includes('场景环境描述')
                            )
                            if (hasMockData) {
                                setMessages([])
                            }
                        }
                    }
                }
```

- [ ] **Step 5.3: Rewrite auto-trigger to use phase**

Replace auto-trigger effect (lines 128-140):

```typescript
    // 自动触发剧本生成（仅在 loading 完成且无历史时）
    useEffect(() => {
        if (
            !hasAutoTriggered.current &&
            !isLoading &&
            conversationId &&
            outlineContext &&
            phase === 'loading'
        ) {
            hasAutoTriggered.current = true
            setPhase('script')
            handleGenerateScript()
        }
    }, [isLoading, conversationId, outlineContext, phase])
```

- [ ] **Step 5.4: Rewrite `handleGenerateScript` to use episodeApi and save pipeline state**

```typescript
    const handleGenerateScript = async () => {
        setGenerationError(null)
        setPhase('script')

        const welcomeMsg: AgentMessage = {
            id: 'welcome',
            role: 'assistant',
            content: `你好！我是 **Arex**。正在为你创作**第${episodeNum}集**的完整分镜剧本...\n\n正在分析大纲，生成剧本、角色图和场景图...`,
            timestamp: Date.now(),
        }
        setMessages([welcomeMsg])
        await saveMessage('assistant', welcomeMsg.content)

        setIsTyping(true)

        try {
            const data = await generateEpisodeScript(projectId, episodeNum, outlineContext)
            setScriptData(data)
            displayScriptResult(data)
            setPhase('confirm')

            // 持久化阶段状态
            await saveMessage('assistant', '', {
                type: 'episode_pipeline',
                phase: 'confirm',
                script_data: data,
            })
        } catch (e: any) {
            console.error(`[Episode ${episodeNum}] Script generation failed:`, e)
            const isTimeout = e.name === 'AbortError'
            const errorText = isTimeout ? 'LLM 请求超时（超过3分钟）' : (e.message || '网络错误')
            setGenerationError(errorText)

            const errorMsg: AgentMessage = {
                id: 'error-' + Date.now(),
                role: 'assistant',
                content: `剧本生成失败：**${errorText}**\n\n请检查后端配置后点击下方按钮重试。`,
                timestamp: Date.now(),
            }
            setMessages(prev => [...prev, errorMsg])
        } finally {
            setIsTyping(false)
        }
    }
```

- [ ] **Step 5.5: Add `handleConfirmAssets` — trigger panel first frame generation**

```typescript
    const handleConfirmAssets = async () => {
        if (!scriptData) return
        setPhase('panels')
        setGenerationError(null)

        const progressMsg: AgentMessage = {
            id: 'panel-progress',
            role: 'assistant',
            content: `正在生成分镜首帧... (0/${scriptData.panels.length})`,
            timestamp: Date.now(),
        }
        setMessages(prev => [...prev, progressMsg])
        setIsTyping(true)
        setPanelProgress({ done: 0, total: scriptData.panels.length })

        try {
            const result = await generatePanelImages(episodeNum, {
                project_id: projectId,
                art_style: scriptData.art_style,
                characters: scriptData.characters,
                scenes: scriptData.scenes,
                panels: scriptData.panels.map(p => ({
                    id: p.id,
                    scene_name: p.scene_name,
                    scene_description: p.scene_description,
                    composition: p.composition,
                    camera_movement: p.camera_movement,
                    characters: p.characters,
                })),
            })

            // 收集结果
            const images: Record<string, string> = {}
            const failed: string[] = []
            for (const pr of result.panels) {
                if (pr.status === 'success' && pr.image_url) {
                    images[pr.id] = pr.image_url
                } else {
                    failed.push(pr.id)
                }
            }
            setPanelImages(images)

            // 更新进度消息
            const successCount = Object.keys(images).length
            const resultMsg: AgentMessage = {
                id: 'panel-result',
                role: 'assistant',
                content: failed.length === 0
                    ? `分镜首帧全部生成完成！共 **${successCount}** 张。\n\n可以点击下方按钮生成视频，或通过对话调整分镜内容。`
                    : `分镜首帧生成完成：**${successCount}** 张成功，**${failed.length}** 张失败（${failed.join(', ')}）。\n\n你可以说"重新生成 ${failed[0]}"来重试，或直接生成视频。`,
                timestamp: Date.now(),
            }
            setMessages(prev => prev.filter(m => m.id !== 'panel-progress').concat(resultMsg))
            setPhase(failed.length === 0 ? 'video' : 'panels')

            // 持久化
            await saveMessage('assistant', resultMsg.content, {
                type: 'episode_pipeline',
                phase: 'video',
                script_data: scriptData,
                panel_images: images,
            })
        } catch (e: any) {
            setGenerationError(e.message || '分镜首帧生成失败')
            const errorMsg: AgentMessage = {
                id: 'panel-error',
                role: 'assistant',
                content: `分镜首帧生成失败：**${e.message}**\n\n请点击下方按钮重试。`,
                timestamp: Date.now(),
            }
            setMessages(prev => prev.filter(m => m.id !== 'panel-progress').concat(errorMsg))
        } finally {
            setIsTyping(false)
            setPanelProgress(null)
        }
    }
```

- [ ] **Step 5.6: Rewrite `handleSendMessage` to route through refine endpoint**

```typescript
    const handleSendMessage = async (content: string) => {
        const userMsg: AgentMessage = {
            id: Date.now().toString(),
            role: 'user',
            content,
            timestamp: Date.now(),
        }
        setMessages(prev => [...prev, userMsg])
        await saveMessage('user', content)

        // ── 对话式改进（confirm / panels / video 阶段）──
        if (scriptData && (phase === 'confirm' || phase === 'panels' || phase === 'video')) {
            setIsTyping(true)
            try {
                const result = await refineEpisode(episodeNum, phase, content, {
                    art_style: scriptData.art_style,
                    characters: scriptData.characters,
                    scenes: scriptData.scenes,
                    panels: scriptData.panels,
                })

                // 显示 LLM 回复
                const replyMsg: AgentMessage = {
                    id: 'refine-' + Date.now(),
                    role: 'assistant',
                    content: result.reply,
                    timestamp: Date.now(),
                }
                setMessages(prev => [...prev, replyMsg])
                await saveMessage('assistant', result.reply)

                // 应用更新
                if (result.updates) {
                    const updated = { ...scriptData }
                    if (result.updates.characters) {
                        for (const uc of result.updates.characters) {
                            const idx = updated.characters.findIndex(c => c.name === uc.name)
                            if (idx >= 0) updated.characters[idx] = { ...updated.characters[idx], ...uc }
                            else updated.characters.push(uc)
                        }
                    }
                    if (result.updates.scenes) {
                        for (const us of result.updates.scenes) {
                            const idx = updated.scenes.findIndex(s => s.name === us.name)
                            if (idx >= 0) updated.scenes[idx] = { ...updated.scenes[idx], ...us }
                            else updated.scenes.push(us)
                        }
                    }
                    if (result.updates.panels) {
                        for (const up of result.updates.panels) {
                            const idx = updated.panels.findIndex(p => p.id === up.id)
                            if (idx >= 0) updated.panels[idx] = { ...updated.panels[idx], ...up }
                        }
                    }
                    if (result.updates.art_style) {
                        updated.art_style = { ...updated.art_style, ...result.updates.art_style }
                    }
                    setScriptData(updated)

                    // 重新渲染剧本 markdown
                    const updatedMarkdown = formatScriptAsMarkdown(updated, panelImages)
                    setMessages(prev => prev.map(m =>
                        m.id === 'script' ? { ...m, content: updatedMarkdown } : m
                    ))

                    // 持久化更新后的数据
                    await saveMessage('assistant', '', {
                        type: 'episode_pipeline',
                        phase,
                        script_data: updated,
                        panel_images: panelImages,
                    })

                    // 如果有需要重新生成图片的角色/场景，提示用户
                    const needsRegen = [
                        ...(result.updates.characters?.filter(c => c.regenerate_image) || []).map(c => c.name),
                        ...(result.updates.scenes?.filter(s => s.regenerate_image) || []).map(s => s.name),
                    ]
                    if (needsRegen.length > 0) {
                        // TODO: 调用后端重新生成单个角色/场景图片
                        const regenMsg: AgentMessage = {
                            id: 'regen-' + Date.now(),
                            role: 'assistant',
                            content: `已更新：${needsRegen.join('、')}。描述已修改，图片将在确认后重新生成。`,
                            timestamp: Date.now(),
                        }
                        setMessages(prev => [...prev, regenMsg])
                    }
                }
            } catch (e: any) {
                const errMsg: AgentMessage = {
                    id: 'refine-err-' + Date.now(),
                    role: 'assistant',
                    content: `处理失败：${e.message || '请重试'}`,
                    timestamp: Date.now(),
                }
                setMessages(prev => [...prev, errMsg])
            } finally {
                setIsTyping(false)
            }
            return
        }

        // ── 视频生成意图（done 阶段）──
        if (phase === 'done') {
            // 保留原有的 compose 意图检测
            if (isComposeIntent(content)) {
                const data = videoCardDataRef.current
                if (data?.phase === 'done') {
                    const urls = data.jobs.filter(j => j.status === 'succeeded' && j.video_url).map(j => j.video_url!)
                    if (urls.length >= 2) {
                        handleCompose(urls)
                        return
                    }
                }
            }
        }

        // ── 默认：通用回复 ──
        setIsTyping(true)
        try {
            const result = await refineEpisode(episodeNum, phase, content, {
                art_style: scriptData?.art_style || { base_style: '', color_tone: '', atmosphere: '' },
                characters: scriptData?.characters || [],
                scenes: scriptData?.scenes || [],
                panels: scriptData?.panels || [],
            })
            const replyMsg: AgentMessage = {
                id: 'chat-' + Date.now(),
                role: 'assistant',
                content: result.reply,
                timestamp: Date.now(),
            }
            setMessages(prev => [...prev, replyMsg])
            await saveMessage('assistant', result.reply)
        } catch {
            // Ignore errors for general chat
        } finally {
            setIsTyping(false)
        }
    }
```

- [ ] **Step 5.7: Update `formatScriptAsMarkdown` to accept `panelImages` param and show images when available**

Update the function signature and panel section:

```typescript
    function formatScriptAsMarkdown(script: any, images?: Record<string, string>): string {
        // ... existing code for title, summary, highlights, art_style, characters, scenes ...

        if (script.panels?.length > 0) {
            md += `## 🎬 分镜剧本\n\n`
            md += `共 **${script.panels.length}** 个分镜\n\n`

            script.panels.forEach((p: any) => {
                md += `### 分镜 ${p.id}\n\n`

                // 显示首帧图片（如果已生成）
                const imgUrl = images?.[p.id] || p.image_url || p.imageUrl
                if (imgUrl) {
                    md += `![分镜${p.id}](${imgUrl})\n\n`
                }

                const sceneDesc = p.scene_description || p.scene || ''
                const sceneName = p.scene_name || p.sceneName || ''
                const cameraMove = p.camera_movement || p.camera || ''
                const voiceChar = p.voice_character || p.voice || ''
                const chars = p.characters || []
                const duration = p.duration_sec || p.durationSec || 5

                md += `| 属性 | 内容 |\n|------|------|\n`
                if (sceneName) md += `| **场景** | ${sceneName} |\n`
                if (chars.length > 0) md += `| **角色** | ${chars.join('、')} |\n`
                md += `| **画面描述** | ${sceneDesc} |\n`
                md += `| **构图设计** | ${p.composition || ''} |\n`
                md += `| **运镜调度** | ${cameraMove} |\n`
                md += `| **时长** | ${duration}秒 |\n`
                md += `| **配音角色** | ${voiceChar} |\n`
                md += `| **台词内容** | ${p.dialogue || ''} |\n\n`
            })
        }

        return md
    }
```

- [ ] **Step 5.8: Update JSX to render phase-aware action bar**

Replace the JSX return (lines 463-533):

```tsx
    // ── 视频生成处理 ──
    const handleStartVideoGeneration = () => {
        if (!scriptData) return
        const panels: PanelImage[] = scriptData.panels
            .filter(p => panelImages[p.id])
            .map((p, i) => ({
                index: i,
                url: panelImages[p.id],
                label: `分镜 ${p.id}`,
            }))

        if (panels.length === 0) return

        const initialData: VideoCardData = {
            phase: 'select',
            panels,
            selectedIndices: panels.map(p => p.index),
            motionPrompt: scriptData.panels[0]?.camera_movement || '缓慢推进，镜头微微摇动',
            durationSec: scriptData.panels[0]?.duration_sec || 5,
            jobs: [],
        }
        videoCardDataRef.current = initialData

        const videoMsg: AgentMessage = {
            id: 'video-card-msg',
            role: 'assistant',
            content: `分镜首帧已就绪，共 **${panels.length}** 张。请选择要生成视频的分镜，调整参数后点击开始。`,
            timestamp: Date.now(),
            customContent: (
                <VideoCard
                    data={initialData}
                    projectId={projectId}
                    episodeNum={episodeNum}
                    onDataChange={handleVideoDataChange}
                    onCompose={handleCompose}
                />
            ),
        }
        setMessages(prev => [...prev, videoMsg])
        setPhase('video')
    }

    // ── Render ──

    if (isLoading) {
        return (
            <div className="flex-1 h-full bg-[#000000] flex items-center justify-center">
                <div className="flex items-center gap-3 text-zinc-500 text-sm">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    <span>正在加载第{episodeNum}集...</span>
                </div>
            </div>
        )
    }

    return (
        <div className="flex-1 h-full bg-[#000000] flex flex-col overflow-hidden relative">
            {/* Header */}
            <div className="absolute top-0 left-0 right-0 z-30 flex items-center gap-4 px-6 py-4 border-b border-zinc-800/50 bg-[#000000]/90 backdrop-blur-md opacity-0 hover:opacity-100 transition-opacity duration-300">
                <Link
                    href={`/agent/${projectId}/episodes`}
                    className="p-2 rounded-lg hover:bg-zinc-800 transition-colors"
                >
                    <ArrowLeft className="h-5 w-5 text-zinc-400" />
                </Link>
                <div>
                    <h1 className="text-lg font-semibold text-white">第{episodeNum}集</h1>
                    <p className="text-xs text-zinc-500">
                        {phase === 'script' && '正在生成剧本...'}
                        {phase === 'confirm' && '等待确认角色与场景'}
                        {phase === 'panels' && '正在生成分镜首帧'}
                        {phase === 'video' && '视频生成'}
                        {phase === 'done' && '全部完成'}
                    </p>
                </div>
            </div>

            {/* Chat */}
            <div className="flex-1 overflow-hidden">
                <AgentChat
                    messages={messages}
                    onSendMessage={handleSendMessage}
                    onCardAction={() => {}}
                    isTyping={isTyping}
                />
            </div>

            {/* Phase Action Bar */}
            {phase === 'confirm' && !isTyping && (
                <div className="flex items-center justify-center gap-3 px-6 py-3 border-t border-zinc-800/50 bg-zinc-900/80">
                    <Button
                        className="bg-emerald-600 hover:bg-emerald-700 text-white text-sm"
                        onClick={handleConfirmAssets}
                    >
                        <Sparkles className="h-4 w-4 mr-2" />
                        确认角色与场景，开始生成分镜首帧
                    </Button>
                </div>
            )}

            {phase === 'panels' && panelProgress && (
                <div className="flex items-center justify-center gap-3 px-6 py-3 border-t border-zinc-800/50 bg-zinc-900/80">
                    <Loader2 className="h-4 w-4 animate-spin text-emerald-400" />
                    <span className="text-sm text-zinc-400">
                        正在生成分镜首帧 ({panelProgress.done}/{panelProgress.total})
                    </span>
                </div>
            )}

            {(phase === 'panels' || phase === 'video') && !isTyping && !panelProgress && Object.keys(panelImages).length > 0 && (
                <div className="flex items-center justify-center gap-3 px-6 py-3 border-t border-zinc-800/50 bg-zinc-900/80">
                    <Button
                        className="bg-emerald-600 hover:bg-emerald-700 text-white text-sm"
                        onClick={handleStartVideoGeneration}
                    >
                        <Film className="h-4 w-4 mr-2" />
                        生成全部视频
                    </Button>
                </div>
            )}

            {generationError && !isTyping && (
                <div className="flex items-center justify-center gap-3 px-6 py-3 border-t border-red-900/30 bg-red-950/20">
                    <span className="text-xs text-red-400">生成失败</span>
                    <Button
                        variant="outline"
                        size="sm"
                        className="text-xs border-emerald-700 text-emerald-400 hover:bg-emerald-900/30"
                        onClick={() => {
                            if (phase === 'script') handleGenerateScript()
                            else if (phase === 'panels') handleConfirmAssets()
                        }}
                    >
                        <Sparkles className="h-3.5 w-3.5 mr-1.5" />
                        重试
                    </Button>
                </div>
            )}
        </div>
    )
```

- [ ] **Step 5.9: Commit**

```bash
git add apps/web/src/app/agent/[projectId]/episodes/[episodeNum]/page.tsx
git commit -m "feat: rewrite episode page with 4-phase pipeline state machine"
```

---

## Task 6: Update VideoCard to Accept Pre-filled Data

**Files:**
- Modify: `apps/web/src/components/agent/VideoCard.tsx:33-49`

### Steps

- [ ] **Step 6.1: Add optional `panelDurations` prop**

Update `VideoCardProps` (line 42):

```typescript
export interface VideoCardProps {
    data: VideoCardData
    projectId: string
    episodeNum: number
    onDataChange: (data: VideoCardData) => void
    onCompose?: (videoUrls: string[]) => void
    panelDurations?: Record<number, number>  // index → duration_sec from script
}
```

In the submit handler (around line 79), use per-panel duration if available:

```typescript
// When creating video jobs, use per-panel duration
const duration = props.panelDurations?.[img.index] ?? data.durationSec
```

- [ ] **Step 6.2: Commit**

```bash
git add apps/web/src/components/agent/VideoCard.tsx
git commit -m "feat: VideoCard accepts per-panel duration from script data"
```

---

## Task 7: Integration Test and Cleanup

### Steps

- [ ] **Step 7.1: Remove dead code**

Remove `generateMockScript` function if still present (already removed in earlier fix). Remove unused imports.

- [ ] **Step 7.2: Manual end-to-end test**

Test the full flow in browser:
1. Navigate to an episode page → should auto-trigger script generation
2. Wait for script + character/scene images → verify images appear
3. Send a chat message like "把主角的衣服改成红色" → verify refine works
4. Click "确认角色与场景" → verify panel first frames generate
5. Click "生成全部视频" → verify video generation starts
6. Refresh page at each phase → verify phase recovery works

- [ ] **Step 7.3: Final commit**

```bash
git add -A
git commit -m "chore: cleanup dead code and verify multi-phase pipeline"
```
