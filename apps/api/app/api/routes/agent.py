"""Agent API - 为前端 Agent（聊天+卡片）提供服务端能力

目前提供：
- 输入用户创意生成「策划大纲」
- 基于策划大纲生成第 1 集分镜剧本（DeepSeek / OpenAI 兼容协议）

注意：本接口只负责 LLM 生成，不直接写入 DB。
前端可继续调用 chaptersApi.create/saveScript/createStoryboard 进行落库与分镜任务触发。
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import json
import logging
import asyncio
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.project import Project
from app.schemas.agent_commit import (
    CommitToStudioRequest,
    CommitToStudioResponse,
    CommitCreatedCounts,
)
from app.services.agent_commit import commit_agent_to_studio
from app.services.brain.standard_llm import StandardLLMService
from app.services.layer_factory.doubao_image_provider import (
    get_doubao_image_provider,
    DoubaoImageRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class OutlineRequest(BaseModel):
    prompt: str
    template: str | None = None
    multi_episode: bool | None = None


class EpisodeInfo(BaseModel):
    number: int
    title: str
    summary: str


class OutlineResponse(BaseModel):
    title: str
    outlineText: str
    episodes: list[EpisodeInfo] = []


class Episode1Request(BaseModel):
    outline_text: str


class Episode1Response(BaseModel):
    episodeTitle: str
    scriptText: str


# ============ 意图识别 API ============

class IntentRequest(BaseModel):
    user_message: str
    has_outline: bool = False
    conversation_context: list[dict] | None = None  # 最近几条消息


class IntentResponse(BaseModel):
    intent: str  # "confirm_outline" | "refine_outline" | "refine_with_input" | "new_topic" | "general_chat"
    confidence: float
    reason: str


@router.post("/intent", response_model=IntentResponse)
async def classify_intent(req: IntentRequest):
    """
    使用 LLM 判断用户意图：
    - confirm_outline: 用户想确认当前大纲
    - refine_outline: 用户想修改大纲，但没说具体怎么改
    - refine_with_input: 用户提供了具体的修改方向/指令
    - new_topic: 用户想讨论新话题或重新开始
    - general_chat: 一般性聊天或提问
    """
    llm = StandardLLMService()

    # 构建上下文
    context_str = ""
    if req.conversation_context:
        for msg in req.conversation_context[-5:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")[:300]
            context_str += f"[{role}]: {content}\n"

    system_prompt = """你是一个意图分类器。分析用户消息，判断其意图。

当前状态：用户已有一份策划大纲。

可能的意图（按优先级判断）：

1. confirm_outline - 用户想确认/通过当前大纲，准备进入下一步
   示例：确认、同意、可以、OK、好的、没问题、开始、继续、确定、通过、就这样、满意、我确认

2. refine_with_input - 用户**已经提供了具体的修改方向或内容**（这是关键！）
   示例：
   - "美术风格方面我想要更文艺的气息" → 用户明确说了要改什么（美术风格）和怎么改（更文艺）
   - "把主角改成女性" → 明确的修改指令
   - "加一个反派角色" → 具体的添加内容
   - "第二集的情节改成他们在咖啡馆相遇" → 具体修改

3. refine_outline - 用户想修改大纲，但**没有提供具体怎么改**
   示例：
   - "我想修改一下" → 没说改什么
   - "再改改" → 没说改什么
   - "不太满意" → 只是表达态度，没说具体问题

4. new_topic - 用户想讨论完全不同的新话题或重新开始

5. general_chat - 一般性聊天、提问或其他

**重要判断规则**：
- 如果用户消息中包含"具体内容/方向"（如风格、角色、情节的描述），选择 refine_with_input
- 如果用户只是表达"想改"但没说改成什么样，选择 refine_outline

只返回 JSON：{"intent": "...", "confidence": 0.0-1.0, "reason": "判断理由"}"""

    user_prompt = f"""最近对话：
{context_str}

用户最新消息："{req.user_message}"

当前是否有大纲：{req.has_outline}

判断用户意图："""

    try:
        content = await llm._chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format="json",
        )

        data = _safe_json_loads(content)

        intent = data.get("intent", "general_chat")
        confidence = float(data.get("confidence", 0.5))
        reason = data.get("reason", "")

        # 验证意图值
        valid_intents = ["confirm_outline", "refine_outline", "refine_with_input", "new_topic", "general_chat"]
        if intent not in valid_intents:
            intent = "general_chat"

        return IntentResponse(intent=intent, confidence=confidence, reason=reason)

    except Exception as e:
        logger.error(f"Intent classification failed: {e}", exc_info=True)
        # 回退到简单关键词匹配
        msg_lower = req.user_message.lower()
        if any(kw in msg_lower for kw in ["确认", "同意", "可以", "ok", "好的", "没问题", "开始", "继续"]):
            return IntentResponse(intent="confirm_outline", confidence=0.6, reason="关键词匹配")
        # 检查是否有具体修改内容（包含名词+形容词/动词的模式）
        elif len(req.user_message) > 10 and any(kw in msg_lower for kw in ["风格", "角色", "情节", "场景", "改成", "加一个", "删除", "添加"]):
            return IntentResponse(intent="refine_with_input", confidence=0.6, reason="关键词匹配-有具体内容")
        elif any(kw in msg_lower for kw in ["修改", "调整", "改", "重新", "完善", "优化"]):
            return IntentResponse(intent="refine_outline", confidence=0.6, reason="关键词匹配")
        return IntentResponse(intent="general_chat", confidence=0.5, reason="默认回退")


# ============ 大纲优化 API ============

class RefineOutlineRequest(BaseModel):
    original_outline: str
    user_refinement: str  # 用户的具体修改方向/指令


class RefineOutlineResponse(BaseModel):
    title: str
    outlineText: str
    changes_summary: str  # 简要说明做了哪些修改


@router.post("/refine-outline", response_model=RefineOutlineResponse)
async def refine_outline(req: RefineOutlineRequest):
    """
    根据用户的具体修改指令优化大纲
    """
    if not req.original_outline.strip():
        raise HTTPException(status_code=400, detail="original_outline is required")
    if not req.user_refinement.strip():
        raise HTTPException(status_code=400, detail="user_refinement is required")

    llm = StandardLLMService()

    system_prompt = """你是专业的AI漫剧策划/编剧总监。你的任务是：根据用户的修改意见，优化现有的策划大纲。

输出要求：
1) 只返回 JSON 对象：{ "title": string, "outlineText": string, "changes_summary": string }
2) 保持原大纲的结构和大部分内容，只根据用户的意见进行针对性修改
3) changes_summary 简要说明做了哪些修改（1-2句话）
4) 不要输出任何额外文字或 Markdown 标记"""

    user_prompt = f"""原始大纲：
{req.original_outline}

用户修改意见：{req.user_refinement}

请根据用户意见优化大纲："""

    try:
        content = await llm._chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format="json",
        )

        data = _safe_json_loads(content)
        title = (data.get("title") or "").strip()
        outline_text = (data.get("outlineText") or "").strip()
        changes_summary = (data.get("changes_summary") or "已根据您的意见优化大纲").strip()

        if not title or not outline_text:
            raise ValueError("Invalid LLM output: missing title/outlineText")

        return RefineOutlineResponse(
            title=title,
            outlineText=outline_text,
            changes_summary=changes_summary
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Outline refinement failed: {e}", exc_info=True)
        if settings.DEBUG:
            raise HTTPException(status_code=500, detail=str(e))
        raise HTTPException(status_code=500, detail="Outline refinement failed")


def _safe_json_loads(content: str) -> dict:
    content = content.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(content)
    except Exception:
        import re

        m = re.search(r"\{[\s\S]*\}", content)
        if not m:
            raise
        return json.loads(m.group(0))


def _extract_episodes_from_outline(outline_text: str) -> list[EpisodeInfo]:
    """从大纲文本中提取集数信息"""
    import re
    
    episodes = []
    # 匹配常见的集数格式: 第1集、第一集、Episode 1、E1等
    patterns = [
        r'第(\d+)集[：:]?\s*([^\n]+)',
        r'第([一二三四五六七八九十]+)集[：:]?\s*([^\n]+)',
        r'Episode\s*(\d+)[：:]?\s*([^\n]+)',
        r'E(\d+)[：:]?\s*([^\n]+)',
    ]
    
    chinese_nums = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, 
                   '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
    
    for pattern in patterns:
        matches = re.findall(pattern, outline_text, re.IGNORECASE)
        for match in matches:
            num_str, title = match
            # 转换中文数字
            if num_str in chinese_nums:
                num = chinese_nums[num_str]
            else:
                try:
                    num = int(num_str)
                except:
                    continue
            
            # 避免重复
            if not any(e.number == num for e in episodes):
                episodes.append(EpisodeInfo(
                    number=num,
                    title=f"第{num}集：{title.strip()}",
                    summary=title.strip()
                ))
    
    # 按集数排序
    episodes.sort(key=lambda x: x.number)
    
    # 如果没有找到，返回默认3集
    if not episodes:
        episodes = [
            EpisodeInfo(number=1, title="第1集", summary="开篇"),
            EpisodeInfo(number=2, title="第2集", summary="发展"),
            EpisodeInfo(number=3, title="第3集", summary="高潮与结局"),
        ]
    
    return episodes


@router.post("/outline", response_model=OutlineResponse)
async def generate_outline(req: OutlineRequest):
    """输入用户创意/想法，生成可用于后续剧本与分镜的策划大纲。"""

    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is required")

    llm = StandardLLMService()

    style_hint = (req.template or "").strip()
    multi_episode = bool(req.multi_episode) if req.multi_episode is not None else False

    system_prompt = (
        "你是专业的AI漫剧策划/编剧总监。你的任务是：基于用户的自然语言想法，生成一份可执行的『策划剧本大纲』。\n\n"
        "输出要求：\n"
        "1) 只返回 JSON 对象，严格遵循 schema：{ \"title\": string, \"outlineText\": string }。不要输出任何额外文字。\n"
        "2) outlineText 必须包含：\n"
        "   - 基础信息（题材/风格/受众/叙事视角）\n"
        "   - 主要角色设定（姓名、身份、动机、关系张力）\n"
        "   - 世界观/时间地点/核心冲突\n"
        "   - 故事主线与节奏（起承转合）\n"
        "   - 章节/分集概要：至少 3 集（如果 multi_episode=true 则给 8-12 集概要）\n"
        "     每集格式必须是：第N集：标题 - 内容概要\n"
        "   - 画面与镜头风格建议（韩漫条漫、情绪、构图关键词）\n"
        "3) 语言：中文。风格偏商业可落地，条理清晰，使用分点与小标题。\n"
    )

    user_prompt = "用户想法如下：\n\n" + req.prompt.strip()
    if style_hint:
        user_prompt += f"\n\n用户选择的模板/风格偏好：{style_hint}"
    user_prompt += f"\n\n是否多集：{str(multi_episode).lower()}"

    try:
        content = await llm._chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format="json",
        )

        data = _safe_json_loads(content)
        title = (data.get("title") or "").strip()
        outline_text = (data.get("outlineText") or "").strip()

        if not title or not outline_text:
            raise ValueError("Invalid LLM output: missing title/outlineText")

        # 从大纲中提取集数信息
        episodes = _extract_episodes_from_outline(outline_text)

        return OutlineResponse(title=title, outlineText=outline_text, episodes=episodes)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent outline generation failed: {e}", exc_info=True)
        if settings.DEBUG:
            raise HTTPException(status_code=500, detail=str(e))
        raise HTTPException(status_code=500, detail="Agent outline generation failed")


@router.post("/episode1", response_model=Episode1Response)
async def generate_episode1_script(req: Episode1Request):
    """输入策划大纲，生成第1集分镜剧本（返回 episodeTitle + scriptText）。"""

    if not req.outline_text.strip():
        raise HTTPException(status_code=400, detail="outline_text is required")

    llm = StandardLLMService()

    system_prompt = (
        "你是专业的AI漫剧导演/编剧智能体。你的任务是：基于用户的策划大纲，为第1集输出可直接用于分镜生成的『分镜剧本』。\n\n"
        "要求：\n"
        "1) 先给出 episodeTitle（例如：第1集：雨中初遇与书店情缘）\n"
        "2) 输出 scriptText：包含场景划分与分镜条目。每条分镜必须包含：画面描述、构图设计、运镜调度、配音角色、台词内容。\n"
        "3) 风格：韩漫二次元、都市情感，镜头语言细腻。\n"
        "4) 分镜数量建议 12-24 格。\n"
        "5) 只返回 JSON 对象，严格遵循 schema：{ \"episodeTitle\": string, \"scriptText\": string }。不要输出任何额外文字。"
    )

    user_prompt = f"策划大纲如下：\n\n{req.outline_text}"

    try:
        content = await llm._chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format="json",
        )

        data = _safe_json_loads(content)

        episode_title = (data.get("episodeTitle") or "").strip()
        script_text = (data.get("scriptText") or "").strip()

        if not episode_title or not script_text:
            raise ValueError("Invalid LLM output: missing episodeTitle/scriptText")

        return Episode1Response(episodeTitle=episode_title, scriptText=script_text)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent episode1 generation failed: {e}", exc_info=True)
        if settings.DEBUG:
            raise HTTPException(status_code=500, detail=str(e))
        raise HTTPException(status_code=500, detail="Agent episode1 generation failed")


# ============ 新增：完整分集剧本生成 API ============

class EpisodeScriptRequest(BaseModel):
    project_id: str
    episode_number: int
    outline_text: str
    conversation_context: list[dict] | None = None  # 可选的对话上下文


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
    time_of_day: str = "day"   # day/night/dawn/dusk
    weather: str = "clear"     # clear/rain/snow/cloudy


class Highlight(BaseModel):
    title: str
    description: str


class ArtStyle(BaseModel):
    base_style: str
    color_tone: str
    atmosphere: str


class Character(BaseModel):
    name: str
    description: str
    visual_prompt: str = ""
    image_url: Optional[str] = None  # 豆包生成的角色参考图


class Scene(BaseModel):
    name: str
    description: str
    visual_prompt: str = ""
    image_url: Optional[str] = None  # 豆包生成的场景参考图


class EpisodeScriptResponse(BaseModel):
    episode_number: int
    episode_title: str
    story_summary: str
    highlights: list[Highlight]
    art_style: ArtStyle
    characters: list[Character]
    scenes: list[Scene]
    panels: list[StoryboardPanel]


# ============ 分镜首帧生成 API ============

class PanelInput(BaseModel):
    id: str
    scene_name: str = ""
    scene_description: str
    composition: str = ""
    camera_movement: str = ""
    characters: list[str] = []

class GeneratePanelsRequest(BaseModel):
    project_id: Optional[str] = None
    conversation_id: Optional[str] = None
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


@router.post("/episode/{episode_number}/script", response_model=EpisodeScriptResponse)
async def generate_full_episode_script(
    episode_number: int,
    req: EpisodeScriptRequest
):
    """
    生成完整的分集剧本，包含：
    - 故事梗概
    - 剧本亮点
    - 美术风格
    - 角色列表
    - 场景列表
    - 分镜剧本
    """
    if not req.outline_text.strip():
        raise HTTPException(status_code=400, detail="outline_text is required")

    llm = StandardLLMService()

    # 构建上下文提示（包含对话历史）
    context_hint = ""
    if req.conversation_context:
        context_hint = "\n\n用户之前的偏好和反馈：\n"
        for msg in req.conversation_context[-10:]:  # 只取最近10条
            role = msg.get("role", "user")
            content = msg.get("content", "")[:500]  # 限制长度
            context_hint += f"[{role}]: {content}\n"

    system_prompt = f"""你是专业的AI漫剧导演/编剧智能体。任务：基于策划大纲，为第{episode_number}集生成完整的分镜剧本。

输出要求（严格JSON格式）：
{{
  "episode_title": "第{episode_number}集：标题",
  "story_summary": "200-300字的故事梗概",
  "highlights": [
    {{"title": "亮点1标题", "description": "亮点描述，包含关键画面和情感"}},
    {{"title": "亮点2标题", "description": "亮点描述"}},
    {{"title": "亮点3标题", "description": "亮点描述"}}
  ],
  "art_style": {{
    "base_style": "韩漫二次元/其他",
    "color_tone": "色调描述",
    "atmosphere": "整体氛围描述"
  }},
  "characters": [
    {{"name": "角色名", "description": "角色设定描述", "visual_prompt": "用于AI绘画的外观描述词（英文）"}}
  ],
  "scenes": [
    {{
      "name": "标准场景名",
      "description": "场景描述",
      "visual_prompt": "用于AI绘画的场景描述词（英文）",
      "possible_variants": ["夜晚", "雨天"]
    }}
  ],
  "panels": [
    {{
      "id": "{str(episode_number).zfill(2)}-1",
      "scene_name": "标准场景名（必须是scenes列表中的名称）",
      "time_of_day": "day/night/dawn/dusk",
      "weather": "clear/rain/snow/cloudy",
      "scene_description": "画面描述，详细描述当前分镜的内容",
      "composition": "构图设计（全景/中景/近景/特写，视角，机位）",
      "camera_movement": "运镜调度（固定镜头/推/拉/摇/跟）",
      "characters": ["角色名1", "角色名2"],
      "voice_character": "配音角色（旁白/角色名）",
      "dialogue": "台词内容",
      "duration_sec": 5
    }}
  ]
}}

场景规范：
1. scenes 列表：每个场景必须有唯一的标准名称（如"杂货铺内部"），不含天气/时间修饰词
2. panels 中的 scene_name 必须是 scenes 列表中的标准名称
3. panels 中用 time_of_day 和 weather 字段表示场景变体

分镜数量：12-24格
每个分镜需要指定 duration_sec（3-10秒），根据画面内容和节奏调整：
- 对话场景：4-6秒
- 动作场景：3-4秒
- 情感特写：5-7秒
- 全景建立镜头：6-8秒
风格要求：韩漫二次元、都市情感、镜头语言细腻
只返回JSON，不要添加任何额外文字或markdown标记。
"""

    user_prompt = f"策划大纲：\n\n{req.outline_text}"
    if context_hint:
        user_prompt += context_hint

    try:
        content = await llm._chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format="json",
        )

        data = _safe_json_loads(content)

        # 解析响应
        episode_title = data.get("episode_title", f"第{episode_number}集")
        story_summary = data.get("story_summary", "")
        
        highlights = [
            Highlight(title=h.get("title", ""), description=h.get("description", ""))
            for h in data.get("highlights", [])
        ]
        
        art_style = ArtStyle(
            base_style=data.get("art_style", {}).get("base_style", "韩漫二次元"),
            color_tone=data.get("art_style", {}).get("color_tone", "柔和温暖"),
            atmosphere=data.get("art_style", {}).get("atmosphere", "细腻唯美")
        )
        
        characters = [
            Character(
                name=c.get("name", ""),
                description=c.get("description", ""),
                visual_prompt=c.get("visual_prompt", "")
            )
            for c in data.get("characters", [])
        ]
        
        scenes = [
            Scene(
                name=s.get("name", ""),
                description=s.get("description", ""),
                visual_prompt=s.get("visual_prompt", "")
            )
            for s in data.get("scenes", [])
        ]
        
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
                time_of_day=p.get("time_of_day", "day"),
                weather=p.get("weather", "clear"),
            )
            for i, p in enumerate(data.get("panels", []))
        ]

        # =========== 生成角色参考图 + 场景参考图 ===========
        art_style_hint = f"{art_style.base_style}, {art_style.color_tone}, {art_style.atmosphere}"

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

        return EpisodeScriptResponse(
            episode_number=episode_number,
            episode_title=episode_title,
            story_summary=story_summary,
            highlights=highlights,
            art_style=art_style,
            characters=characters,
            scenes=scenes,
            panels=panels
        )

    except HTTPException:
        raise
    except ValueError as e:
        # Config errors (missing API key, empty base_url) — always show detail
        logger.error(f"Agent episode script config error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Agent episode script generation failed: {e}", exc_info=True)
        # Include error class name for easier debugging even in production
        detail = f"{type(e).__name__}: {e}" if settings.DEBUG else f"Episode script generation failed ({type(e).__name__})"
        raise HTTPException(status_code=500, detail=detail)


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
                if not (result.success and result.image_url):
                    return PanelResult(
                        id=panel.id,
                        status="failed",
                        error=result.error or "Generation returned no image",
                    )

                # Persist Doubao temp URL to MinIO immediately so downstream
                # consumers (commit-to-studio, asset hub) can rely on the key.
                try:
                    from app.services.agent_commit.image_fetcher import (
                        fetch_and_persist,
                        ImageFetchError,
                    )
                    project_id_for_path = getattr(req, "project_id", None) or "unknown"
                    minio_key = await fetch_and_persist(
                        result.image_url,
                        project_id=project_id_for_path,
                        asset_type="panel",
                        name_hint=f"ep{episode_number}-p{panel.id}",
                    )
                    return PanelResult(id=panel.id, image_url=minio_key, status="success")
                except ImageFetchError as persist_err:
                    logger.warning(
                        f"[Episode {episode_number}] Panel '{panel.id}' MinIO persist failed; "
                        f"returning temp URL: {persist_err}"
                    )
                    return PanelResult(
                        id=panel.id,
                        image_url=result.image_url,
                        status="success",
                        error=f"minio persist failed: {persist_err}",
                    )
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

    # Persist to conversation as `panels` card for later lean-payload commit
    conversation_id = getattr(req, "conversation_id", None)
    if conversation_id:
        try:
            from app.services.agent_commit.card_writer import upsert_card, build_panels_card
            from app.core.database import SessionLocal

            result_by_id = {r.id: r for r in panel_results}
            merged_panels = []
            for p in req.panels:
                r = result_by_id.get(p.id)
                merged_panels.append({
                    "id": p.id,
                    "order": getattr(p, "order", None),
                    "scene_name": p.scene_name,
                    "characters": p.characters,
                    "scene_description": p.scene_description,
                    "dialogue": getattr(p, "dialogue", None),
                    "shot_type": getattr(p, "shot_type", "MS"),
                    "camera_angle": getattr(p, "camera_angle", "eye-level"),
                    "emotion": getattr(p, "emotion", None),
                    "composition": p.composition,
                    "image_url": r.image_url if r and r.status == "success" else None,
                })

            db = SessionLocal()
            try:
                success_count = sum(1 for r in panel_results if r.status == "success")
                upsert_card(
                    db, conversation_id, "panels",
                    build_panels_card(merged_panels),
                    episode_number=episode_number,
                    content_text=f"[panels card · ep{episode_number} · {success_count}/{len(panel_results)} ready]",
                )
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to write panels card: {e}")

    return GeneratePanelsResponse(panels=panel_results)


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
