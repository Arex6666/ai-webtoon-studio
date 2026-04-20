"""
Standard LLM Service - 支持 OpenAI 兼容接口的模型服务 (OpenAI, Deepseek, Tongyi, Doubao)
"""
import httpx
import json
import logging
from typing import Dict, Any, List, Optional, AsyncGenerator

from app.core.config import settings
from .base import BaseBrainService

logger = logging.getLogger(__name__)


class StandardLLMService(BaseBrainService):
    """通用 LLM 服务 (OpenAI 协议兼容)"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        # 使用 effective_* 属性自动根据 LLM_PROVIDER 选择配置
        self.api_key = api_key or settings.effective_llm_api_key
        self.model = model or settings.effective_llm_model
        self.base_url = (base_url or settings.effective_llm_base_url).rstrip("/")
        self.provider = settings.LLM_PROVIDER

        if not self.base_url:
            raise ValueError("LLM base_url is empty")

        # 没配置 key 时，避免发出无意义请求（Bearer None），让上层决定是否降级到 Mock
        if not self.api_key:
            logger.warning("LLM API key is not set; StandardLLMService will not be able to call provider.")

    async def _chat_completion(
        self,
        messages: List[Dict[str, str]],
        response_format: str = "text"
    ) -> str:
        """调用 LLM API"""
        if not self.api_key:
            raise ValueError("LLM API key is not set")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 特殊头部处理
        if self.provider == "deepseek":
            pass # Deepseek 通常兼容 OpenAI
            
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7
        }
        
        # JSON 模式支持检测
        if response_format == "json":
            # 大部分兼容 OpenAI 的新模型支持 json_object
            if self.provider in ["openai", "deepseek", "doubao"]:
                try:
                    payload["response_format"] = {"type": "json_object"}
                except:
                    pass
            else:
                # 如果不支持 json_object，通过 Prompt 强制
                sys_msg = next((m for m in messages if m["role"] == "system"), None)
                if sys_msg:
                    sys_msg["content"] += "\n请务必只返回纯 JSON 格式，不要包含 Markdown 标记。"
        
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )

                if response.status_code != 200:
                    body = response.text
                    # 避免错误体过长/泄露过多细节
                    if body and len(body) > 2000:
                        body = body[:2000] + "..."
                    logger.error(f"LLM API Error: status={response.status_code} body={body}")
                    response.raise_for_status()

                data = response.json()
                content = data["choices"][0]["message"]["content"]

                # 清理可能的 Markdown 标记
                if response_format == "json":
                    content = content.replace("```json", "").replace("```", "").strip()

                return content

        except Exception as e:
            logger.error(f"LLM request failed: {e}", exc_info=True)
            raise

    async def _stream_chat_completion(
        self,
        messages: List[Dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """流式调用 LLM API (SSE)
        
        Args:
            messages: 消息列表
            
        Yields:
            响应内容块
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "stream": True  # 启用流式
        }
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        logger.error(f"LLM Stream API Error: {error_text.decode()}")
                        raise Exception(f"LLM API Error: {response.status_code}")
                    
                    async for line in response.aiter_lines():
                        # SSE 格式: data: {...}
                        if not line.startswith("data: "):
                            continue
                        
                        data = line[6:]  # 移除 "data: " 前缀
                        
                        # 流结束标志
                        if data.strip() == "[DONE]":
                            break
                        
                        try:
                            chunk = json.loads(data)
                            choices = chunk.get("choices", [])
                            if not choices:
                                continue
                            
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            
                            if content:
                                yield content
                                
                        except json.JSONDecodeError:
                            # 某些行可能不是有效 JSON，跳过
                            continue
                            
        except httpx.TimeoutException:
            logger.error("LLM stream request timed out")
            yield "\n[响应超时，请重试]"
        except Exception as e:
            logger.error(f"LLM stream request failed: {e}")
            raise e

    async def analyze_script(self, script_text: str) -> List[Dict[str, Any]]:
        """分析脚本"""
        system_prompt = """你是一个专业的漫画分镜师。分析给定的剧本文本，将其拆解为适合漫画表现的分镜列表。

对于每个分镜，提供以下信息：
- order: 分镜序号（从0开始）
- action_description: 动作/画面描述（用于AI图像生成，需具体详细）
- dialogue: 对话内容（如果有）
- shot_type: 建议景别（close/medium/full/wide）
- emotion: 情绪基调
- panel_weight: 分镜重要性（highlight/normal/transition）

以 JSON 数组格式返回结果。"""

        user_prompt = f"""请分析以下剧本：

{script_text}

返回 JSON 格式的分镜列表。"""

        try:
            # 临时增加 JSON 提示，以防模型不稳定
            result = await self._chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt + "\nIMPORTANT: Return ONLY valid JSON array."},
                    {"role": "user", "content": user_prompt}
                ],
                response_format="json"
            )
            
            try:
                data = json.loads(result)
            except json.JSONDecodeError:
                # 尝试修复简单的 JSON 错误
                if "```json" in result:
                    result = result.split("```json")[1].split("```")[0].strip()
                    data = json.loads(result)
                else:
                    raise

            return data if isinstance(data, list) else data.get("panels", [])
            
        except Exception as e:
            logger.error(f"Script analysis failed: {e}")
            # 降级到 Mock
            from .mock import MockBrainService
            return await MockBrainService().analyze_script(script_text)

    async def _fallback_parse_from_analysis(self, script_text: str) -> List["ParsedPanel"]:
        """Fallback: convert analyze_script output into ParsedPanel list."""
        from .base import ParsedPanel

        analyzed = await self.analyze_script(script_text)
        panels: List[ParsedPanel] = []

        for i, p in enumerate(analyzed or []):
            panels.append(ParsedPanel(
                panel_index=p.get("order", i),
                action_description=(p.get("action_description") or "").strip(),
                dialogue=p.get("dialogue"),
                shot_type=p.get("shot_type", "medium"),
                camera_angle=p.get("camera_angle", "eye_level"),
                emotion=p.get("emotion", "neutral"),
                characters=p.get("characters", []),
                character_refs=p.get("characters", []),
                scene_description=p.get("scene_description"),
                scene_ref=p.get("scene_ref") or p.get("scene_description"),
                time_of_day=p.get("time_of_day", "day"),
                weather=p.get("weather", "clear"),
                suggested_duration=p.get("suggested_duration", 2.5)
            ))

        return panels

    async def suggest_bubble_positions(
        self,
        panel_spec: Dict[str, Any],
        layer_bbox: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """建议气泡位置"""
        system_prompt = """你是一个专业的漫画排版师。根据分镜规格和角色位置信息，为每个气泡建议最佳放置位置。

考虑因素：
- 气泡不应遮挡角色面部
- 阅读顺序应自然（从上到下、从右到左）
- 思考泡应在角色头顶
- 旁白框通常在顶部或底部

返回 JSON 数组，每项包含：bubble_id, suggested_x, suggested_y, suggested_width, confidence"""

        user_prompt = f"""分镜规格：
{json.dumps(panel_spec, ensure_ascii=False, indent=2)}

角色边界框：
{json.dumps(layer_bbox, ensure_ascii=False, indent=2)}

请建议气泡位置（坐标为0-1的百分比）。"""

        try:
            result = await self._chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format="json"
            )
            
            data = json.loads(result)
            return data if isinstance(data, list) else data.get("suggestions", [])
            
        except Exception as e:
            logger.error(f"Bubble position suggestion failed: {e}")
            from .mock import MockBrainService
            return await MockBrainService().suggest_bubble_positions(panel_spec, layer_bbox)

    async def enhance_prompt(self, base_prompt: str, style: str) -> str:
        """增强提示词"""
        system_prompt = """你是一个AI图像生成专家。优化给定的提示词，使其更适合生成高质量的漫画风格图像。

保持原意，但增加：
- 具体的艺术风格描述
- 质量标签
- 技术细节（光影、构图等）

直接返回优化后的提示词文本，不要添加解释。"""

        user_prompt = f"""原始提示词：{base_prompt}
目标风格：{style}

请优化提示词。"""

        try:
            result = await self._chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            return result.strip()
            
        except Exception as e:
            logger.error(f"Prompt enhancement failed: {e}")
            from .mock import MockBrainService
            return await MockBrainService().enhance_prompt(base_prompt, style)

    async def qa_analyze(
        self,
        panel_spec: Dict[str, Any],
        rendered_images: List[str]
    ) -> Dict[str, Any]:
        """QA 分析 - 目前仅 Mock"""
        from .mock import MockBrainService
        return await MockBrainService().qa_analyze(panel_spec, rendered_images)

    # 暂未实现的方法继续抛出 NotImplemented 或使用 Mock
    async def parse_script(self, script_text: str, style_hint: Optional[str] = None) -> Any:
        """
        使用 LLM 解析剧本为详细分镜（增强版）
        生成丰富的分镜信息用于 AI 图像生成
        """
        from .base import ScriptParseResult, ParsedPanel, ContinuityIssue
        
        style_desc = {
            "korean_webtoon": "韩国条漫风格，清新、细腻、色彩柔和，注重人物情感表达",
            "manga": "日本漫画风格，强调线条、网点效果、黑白对比",
            "manhwa": "浪漫韩漫风格，唯美氛围、柔和光影",
            "comic": "美式漫画风格，色彩饱和、强烈对比、力量感"
        }.get(style_hint, "韩国条漫风格")
        
        system_prompt = f"""你是一位顶尖的漫画分镜师和导演。你的任务是将剧本转化为专业的漫画分镜脚本。

目标风格：{style_desc}

你需要为每个分镜提供极其详细的描述，这些描述将直接用于AI图像生成，因此必须包含：

## 输出格式要求
返回 JSON 对象，包含以下字段：

{{
  "panels": [
    {{
      "panel_index": 0,
      "action_description": "【极其详细】描述画面中发生的动作、人物姿态、表情、服装、环境细节，至少100字",
      "dialogue": "对话内容（如果有）",
      "shot_type": "extreme_close/close/medium/full/wide/extreme_wide",
      "camera_angle": "eye_level/high/low/bird/worm/dutch",
      "emotion": "neutral/happy/sad/angry/surprised/fear/contempt/romantic/tense/mysterious",
      "characters": ["周屿", "林知夏"],
      "scene_ref": "旧书店",
      "scene_description": "场景的详细描述：时间、地点、光线、氛围、背景物品",
      "time_of_day": "dawn/morning/noon/afternoon/dusk/night",
      "weather": "clear/cloudy/rainy/snowy/foggy/stormy",
      "suggested_duration": 2.5,
      "composition_notes": "构图建议：人物位置、视觉焦点、留白区域",
      "lighting_notes": "光影描述：光源方向、光影效果、氛围",
      "panel_weight": "highlight/normal/transition",
      "props_in_panel": ["透明雨伞", "旧书"]
    }}
  ],
  "detected_characters": ["周屿", "林知夏"],
  "detected_scenes": ["旧书店", "咖啡厅"],
  "detected_props": ["透明雨伞", "旧书", "手机"],
  "continuity_notes": "连续性注意事项"
}}

## ⚠️⚠️⚠️ 角色提取规则（严格执行）⚠️⚠️⚠️

### 步骤1：识别真正的角色
在填写 detected_characters 之前，请先回答：
**"这个剧本中，有哪些真正出场的人物？他们的名字是什么？"**

只有满足以下条件的才是角色：
- ✅ 在剧本中有主动行为（如"她说"、"他走进"）
- ✅ 有对白或被称呼
- ✅ 是完整的人物姓名（如"林知夏"、"周屿"、"陈爷爷"）

### 步骤2：绝对禁止提取的内容

| 类型 | 示例（绝对禁止） | 说明 |
|------|------------------|------|
| 对白片段 | 这么好、年冬天、笼才好、提着它、话没、佛在诉、她总 | 从对话中截取的碎片 |
| 动词短语 | 又看了、说了、想着、走了 | 动作词汇 |
| 形容词 | 温和的、安静的、慢慢地 | 修饰语 |
| 占位符 | 角色A、角色B、人物1 | 通用占位符 |
| 代词 | 她、他、自己、大家 | 不是姓名 |
| 时间词 | 傍晚时分、夜晚、那天 | 时间表达 |

### ❌ 错误示例（绝对不要这样做）
```json
"detected_characters": ["角色A", "这么好", "话没", "佛在诉", "年冬天"]
```

### ✅ 正确示例
```json
"detected_characters": ["林知夏", "周屿", "陈爷爷"]
```

## ⚠️⚠️⚠️ 场景提取规则（严格执行）⚠️⚠️⚠️

### 步骤1：识别基础地点
detected_scenes 只填写**简短的地点名称**，不要包含时间、光线、氛围等描述。

### 步骤2：绝对禁止提取的内容

| 类型 | 示例（绝对禁止） | 说明 |
|------|------------------|------|
| 对白片段 | 声又涌了、林晚放、说留着给、笼在暮色 | 从对话截取的碎片 |
| 完整描述句 | 傍晚时分杂货铺柜台前光线昏暗 | 太长 |
| 时间+地点 | 夜晚的街道、傍晚的杂货铺 | 包含时间 |

### ❌ 错误示例（绝对不要这样做）
```json
"detected_scenes": ["声又涌了", "让旧时光", "系在灯笼", "新的一年"]
```

### ✅ 正确示例
```json
"detected_scenes": ["杂货铺", "街道", "巷子"]
```

## 物品识别规则
detected_props 包含剧本中出现的重要物品/道具，如：灯笼、雨伞、书本、手机等

## 分镜创作原则

1. **动作描述必须极其详细**（至少100字）
2. **镜头运用专业**（建立镜头用wide，情感高潮用extreme_close）
3. **构图考虑**（为气泡对话留出空间）
4. **连续性**（服装、道具的一致性）

请确保每个分镜的 action_description 至少包含 100 字的详细描述。"""

        user_prompt = f"""请将以下剧本转化为专业的漫画分镜脚本：

---剧本开始---
{script_text}
---剧本结束---

请生成 JSON 格式的详细分镜列表。每个分镜的 action_description 必须极其详细，因为这会直接用于AI图像生成。"""

        try:
            result = await self._chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format="json"
            )
            
            try:
                data = json.loads(result)
            except json.JSONDecodeError:
                # 尝试修复 JSON
                if "```json" in result:
                    result = result.split("```json")[1].split("```")[0].strip()
                    data = json.loads(result)
                elif "```" in result:
                    result = result.split("```")[1].split("```")[0].strip()
                    data = json.loads(result)
                else:
                    raise
            
            # 转换为 ParsedPanel 对象
            panels = []
            for p in data.get("panels", data if isinstance(data, list) else []):
                panels.append(ParsedPanel(
                    panel_index=p.get("panel_index", len(panels)),
                    action_description=p.get("action_description", ""),
                    dialogue=p.get("dialogue"),
                    shot_type=p.get("shot_type", "medium"),
                    camera_angle=p.get("camera_angle", "eye_level"),
                    emotion=p.get("emotion", "neutral"),
                    characters=p.get("characters", []),
                    character_refs=p.get("characters", []),
                    scene_description=p.get("scene_description"),
                    scene_ref=p.get("scene_description", "").split("：")[0] if p.get("scene_description") else None,
                    time_of_day=p.get("time_of_day", "day"),
                    weather=p.get("weather", "clear"),
                    suggested_duration=p.get("suggested_duration", 2.5)
                ))

            if not panels:
                logger.warning("LLM parse_script returned 0 panels, falling back to analysis-based parsing")
                panels = await self._fallback_parse_from_analysis(script_text)
                if not panels:
                    raise ValueError("LLM parse_script produced zero panels after fallback")
            
            total_duration = sum(p.suggested_duration for p in panels)
            
            logger.info(f"Deepseek parsed script into {len(panels)} detailed panels")
            
            return ScriptParseResult(
                panels=panels,
                detected_characters=data.get("detected_characters", []),
                detected_scenes=data.get("detected_scenes", []),
                detected_props=data.get("detected_props", []),  # S5-04: 物品
                total_duration=total_duration,
                continuity_issues=[]
            )
            
        except Exception as e:
            logger.error(f"LLM parse_script failed: {e}, falling back to mock")
            from .mock import MockBrainService
            return await MockBrainService().parse_script(script_text, style_hint)

    async def check_continuity(self, panels: List[Dict[str, Any]], characters: Optional[Dict[str, Any]] = None, scenes: Optional[Dict[str, Any]] = None) -> Any:
        from .mock import MockBrainService
        return await MockBrainService().check_continuity(panels, characters, scenes)
        
    async def suggest_fix(self, issue: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        return {}

    async def extract_props_and_outfits(self, script_text: str) -> Dict[str, Any]:
        """
        从剧本中提取物品(Props)和服装(Outfits)信息
        
        返回格式:
        {
            "hand_props": [...],      # 手持物品
            "set_dressings": [...],   # 场景陈设
            "outfits": [...],         # 服装变体
            "character_prop_relations": [...]  # 角色-物品关系
        }
        """
        system_prompt = """你是一位专业的美术指导和场记。你的任务是从剧本中提取所有重要的物品、道具和服装信息。

## 提取类别

### 1. 手持物品 (hand_props)
角色手中拿着或使用的物品，例如：
- 手机、书籍、杯子、武器、钥匙
- 任何会与角色互动的物品

### 2. 场景陈设 (set_dressings) 
场景中的重要固定物品，例如：
- 家具（桌椅、沙发）
- 装饰品（画、花瓶）
- 交通工具（汽车、自行车）
- 环境元素（路灯、信号灯）

### 3. 服装 (outfits)
角色的服装搭配，需要记录：
- 穿着者是谁
- 服装名称（如"校服"、"便服"、"正装"）
- 服装描述
- 上衣、下装、鞋子等具体单品

### 4. 角色-物品关系 (character_prop_relations)
记录谁在什么时候使用了什么物品

## 输出格式（JSON）

{
    "hand_props": [
        {
            "canonical_name": "物品标准名称",
            "aliases": ["别名1", "别名2"],
            "visual_brief": "简短的视觉描述",
            "material": "材质",
            "colors": ["颜色1", "颜色2"],
            "shape": "形状描述",
            "key_features": ["特征1", "特征2"],
            "importance": "high/medium/low"
        }
    ],
    "set_dressings": [
        {
            "canonical_name": "物品标准名称",
            "aliases": ["别名"],
            "visual_brief": "简短的视觉描述",
            "material": "材质",
            "colors": ["颜色"],
            "key_features": ["特征"],
            "typical_scenes": ["通常出现的场景"]
        }
    ],
    "outfits": [
        {
            "character_name": "穿着这套服装的角色",
            "outfit_name": "服装名称（如校服、西装）",
            "outfit_description": "完整的服装描述",
            "garment_items": ["上衣", "裤子", "鞋子"],
            "colors": ["主色调"],
            "materials": ["材质"],
            "is_default": true/false
        }
    ],
    "character_prop_relations": [
        {
            "character_name": "角色名",
            "prop_name": "物品名",
            "relation_type": "holds/wears/uses",
            "context": "在什么场景/情境下"
        }
    ]
}

## 提取原则

1. **重要性原则**：只提取对剧情或视觉有影响的物品，忽略无关紧要的背景细节
2. **一致性原则**：使用标准名称，避免模糊描述
3. **可渲染原则**：提供足够详细的视觉描述，以便AI生成参考图
4. **去重原则**：相同物品只记录一次，使用别名合并

请仔细分析剧本，提取所有重要物品信息。"""

        user_prompt = f"""请从以下剧本中提取所有物品、服装信息：

---剧本开始---
{script_text}
---剧本结束---

请返回 JSON 格式的提取结果。"""

        try:
            result = await self._chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format="json"
            )
            
            try:
                data = json.loads(result)
            except json.JSONDecodeError:
                # 尝试修复 JSON
                if "```json" in result:
                    result = result.split("```json")[1].split("```")[0].strip()
                    data = json.loads(result)
                elif "```" in result:
                    result = result.split("```")[1].split("```")[0].strip()
                    data = json.loads(result)
                else:
                    raise

            logger.info(f"Extracted {len(data.get('hand_props', []))} hand props, "
                       f"{len(data.get('set_dressings', []))} set dressings, "
                       f"{len(data.get('outfits', []))} outfits")
            
            return {
                "hand_props": data.get("hand_props", []),
                "set_dressings": data.get("set_dressings", []),
                "outfits": data.get("outfits", []),
                "character_prop_relations": data.get("character_prop_relations", [])
            }
            
        except Exception as e:
            logger.error(f"Prop extraction failed: {e}")
            # 返回空结果而不是失败
            return {
                "hand_props": [],
                "set_dressings": [],
                "outfits": [],
                "character_prop_relations": []
            }
