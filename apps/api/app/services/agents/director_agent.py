"""
DirectorAgent - 导演智能体
统一入口智能体，对外表现为一个助手，对内切换不同模式(编剧/导演/美术/制片/质检)
"""
import logging
from typing import Dict, Any, AsyncGenerator, Optional, List
from enum import Enum
from sqlalchemy.orm import Session

from app.services.agents.base_agent import BaseAgent
from app.services.agents.schema_guard import SchemaGuard, SchemaType
from app.services.agents.patch_generator import PatchGenerator, PatchTarget, Patch, PatchResult
from app.schemas.conversation import IntentAnalysisResult

logger = logging.getLogger(__name__)


class AgentMode(str, Enum):
    """智能体模式"""
    SCRIPTWRITER = "scriptwriter"  # 编剧模式：剧本创作、对白润色
    DIRECTOR = "director"          # 导演模式：分镜规划、镜头语言
    ART_DIRECTOR = "art_director"  # 美术总监：风格、光影、参考策略
    PRODUCER = "producer"          # 制片模式：渲染调度、资源管理
    QA = "qa"                      # 质检模式：质量评估、修复建议


# 各模式的系统提示词
MODE_PROMPTS = {
    AgentMode.SCRIPTWRITER: """你是一位资深的漫画编剧。你的职责是：
1. 理解用户的故事创意并帮助完善
2. 创作生动的对白和旁白
3. 把控故事节奏和情节发展
4. 确保角色性格一致性

请用专业、富有创意的语气与用户交流。在创作时注意：
- 对白要简洁有力，适合气泡展示
- 情节要有起承转合
- 为每个分镜提供足够的视觉描述""",

    AgentMode.DIRECTOR: """你是一位专业的漫画分镜导演。你的职责是：
1. 将故事拆解为具体的分镜画面
2. 设计镜头角度、景别和构图
3. 规划角色走位和动作
4. 确保视觉叙事流畅

请用专业的导演视角与用户交流。注意：
- 镜头要服务于叙事
- 注意视觉连贯性
- 合理使用特写、中景、远景""",

    AgentMode.ART_DIRECTOR: """你是一位经验丰富的美术总监。你的职责是：
1. 确定和统一画面风格
2. 设计角色和场景的视觉表现
3. 把控色彩、光影氛围
4. 确保视觉一致性

请用专业的美术视角与用户交流。关注：
- 风格统一性
- 色彩搭配
- 光影效果
- 细节质感""",

    AgentMode.PRODUCER: """你是一位高效的制片人。你的职责是：
1. 规划渲染工作流程
2. 管理资产和资源
3. 协调各个环节的进度
4. 优化生成效率

请用专业、务实的语气与用户交流。关注：
- 渲染优先级
- 资源复用
- 进度把控""",

    AgentMode.QA: """你是一位严谨的质量检查员。你的职责是：
1. 评估生成图像的质量
2. 识别常见问题(手部、脸部、一致性等)
3. 提供具体的修复建议
4. 确保输出达到发布标准

请用专业、建设性的语气与用户交流。关注：
- 画面质量
- 角色一致性
- 构图问题
- 具体改进建议""",
}


class DirectorAgent(BaseAgent):
    """
    导演智能体 - 统一入口
    
    整合SchemaGuard、PatchGenerator和专业智能体，
    根据用户意图自动切换模式进行处理。
    """

    def __init__(self, db: Optional[Session] = None):
        super().__init__(
            name="director_agent",
            description="AI漫剧创作导演，统一处理各类创作请求",
        )
        self.db = db
        self.mode = AgentMode.DIRECTOR  # 默认导演模式
        
        # 核心组件
        self.schema_guard = SchemaGuard(auto_repair=True)
        self.patch_generator = PatchGenerator()
        
        # 当前工作状态
        self.current_storyboard: Optional[Dict[str, Any]] = None
        self.pending_patches: List[Patch] = []

    def switch_mode(self, mode: AgentMode) -> None:
        """切换智能体模式"""
        logger.info(f"DirectorAgent switching mode from {self.mode} to {mode}")
        self.mode = mode

    def get_system_prompt(self) -> str:
        """获取当前模式的系统提示词"""
        return MODE_PROMPTS.get(self.mode, MODE_PROMPTS[AgentMode.DIRECTOR])

    async def process(
        self,
        user_message: str,
        intent: IntentAnalysisResult,
        context: Dict[str, Any],
        streaming: bool = True,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        处理用户消息的主入口
        
        Args:
            user_message: 用户消息
            intent: 意图分析结果
            context: 对话上下文
            streaming: 是否流式响应
            
        Yields:
            响应事件
        """
        try:
            # 根据意图自动切换模式
            self._auto_switch_mode(intent)

            # 根据意图类型分发处理
            if intent.primary_intent == "script":
                async for event in self._handle_script_intent(user_message, intent, context):
                    yield event
            elif intent.primary_intent == "asset":
                async for event in self._handle_asset_intent(user_message, intent, context):
                    yield event
            elif intent.primary_intent == "render":
                async for event in self._handle_render_intent(user_message, intent, context):
                    yield event
            elif intent.primary_intent == "qa":
                async for event in self._handle_qa_intent(user_message, intent, context):
                    yield event
            else:
                async for event in self._handle_general_intent(user_message, context):
                    yield event

        except Exception as e:
            logger.error(f"DirectorAgent error: {e}", exc_info=True)
            yield {
                "type": "error",
                "error": str(e),
            }

    def _auto_switch_mode(self, intent: IntentAnalysisResult) -> None:
        """根据意图自动切换模式"""
        mode_mapping = {
            "script": AgentMode.SCRIPTWRITER,
            "asset": AgentMode.ART_DIRECTOR,
            "render": AgentMode.PRODUCER,
            "qa": AgentMode.QA,
            "general": AgentMode.DIRECTOR,
        }
        new_mode = mode_mapping.get(intent.primary_intent, AgentMode.DIRECTOR)
        if new_mode != self.mode:
            self.switch_mode(new_mode)

    async def _handle_script_intent(
        self,
        user_message: str,
        intent: IntentAnalysisResult,
        context: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """处理剧本/分镜相关意图"""
        # 检查是否是创建新分镜
        if self._is_create_storyboard(user_message):
            async for event in self._create_storyboard(user_message, context):
                yield event
        # 检查是否是修改现有分镜
        elif self._is_modify_storyboard(user_message) and self.current_storyboard:
            async for event in self._modify_storyboard(user_message, context):
                yield event
        else:
            # 一般剧本讨论
            async for event in self._chat_response(user_message, context):
                yield event

    async def _handle_asset_intent(
        self,
        user_message: str,
        intent: IntentAnalysisResult,
        context: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """处理资产相关意图"""
        yield {
            "type": "message",
            "content": "🎨 [美术总监模式]\n\n正在分析您的资产需求...",
        }
        
        # 使用LLM分析资产需求并生成响应
        response = await self._call_llm(
            user_message=user_message,
            system_prompt=self.get_system_prompt(),
            context=context,
        )
        
        yield {
            "type": "message",
            "content": response,
        }

    async def _handle_render_intent(
        self,
        user_message: str,
        intent: IntentAnalysisResult,
        context: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """处理渲染相关意图"""
        yield {
            "type": "message",
            "content": "🎬 [制片模式]\n\n正在规划渲染任务...",
        }
        
        response = await self._call_llm(
            user_message=user_message,
            system_prompt=self.get_system_prompt(),
            context=context,
        )
        
        yield {
            "type": "message",
            "content": response,
        }

    async def _handle_qa_intent(
        self,
        user_message: str,
        intent: IntentAnalysisResult,
        context: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """处理质检相关意图"""
        yield {
            "type": "message",
            "content": "🔍 [质检模式]\n\n正在分析质量问题...",
        }
        
        response = await self._call_llm(
            user_message=user_message,
            system_prompt=self.get_system_prompt(),
            context=context,
        )
        
        yield {
            "type": "message",
            "content": response,
        }

    async def _handle_general_intent(
        self,
        user_message: str,
        context: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """处理一般意图"""
        response = await self._call_llm(
            user_message=user_message,
            system_prompt=self.get_system_prompt(),
            context=context,
        )
        
        yield {
            "type": "message",
            "content": response,
        }

    def _is_create_storyboard(self, message: str) -> bool:
        """判断是否是创建分镜的请求"""
        keywords = ["创建", "生成", "做一个", "帮我", "写一个", "画一个", "四格", "漫画", "故事"]
        return any(kw in message for kw in keywords)

    def _is_modify_storyboard(self, message: str) -> bool:
        """判断是否是修改分镜的请求"""
        keywords = ["修改", "改成", "改为", "换成", "调整", "第", "格"]
        return any(kw in message for kw in keywords)

    async def _create_storyboard(
        self,
        user_message: str,
        context: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """创建分镜"""
        yield {
            "type": "message",
            "content": "📝 [编剧模式]\n\n正在分析您的故事创意，生成分镜规划...",
        }

        # 使用LLM生成分镜JSON
        storyboard_prompt = f"""{self.get_system_prompt()}

请根据用户的故事描述，生成一个分镜规划。返回JSON格式：

{{
  "title": "故事标题",
  "style": "画风描述",
  "characters": [
    {{"name": "角色名", "description": "角色描述", "appearance": "外貌描述"}}
  ],
  "scenes": [
    {{"name": "场景名", "description": "场景描述"}}
  ],
  "panels": [
    {{
      "panel_number": 1,
      "description": "画面描述",
      "dialogue": [{{"speaker": "角色名", "text": "对白内容"}}],
      "camera": {{"angle": "eye_level/top_down/low_angle", "shot_type": "close_up/medium/wide"}},
      "characters": ["角色名"],
      "scene": "场景名",
      "mood": "情绪氛围"
    }}
  ]
}}

只返回JSON，不要其他文字。"""

        messages = [
            {"role": "system", "content": storyboard_prompt},
            {"role": "user", "content": f"故事描述: {user_message}"},
        ]

        try:
            response = await self.llm._chat_completion(messages, response_format="json")
            import json
            storyboard_data = json.loads(response)

            # 使用SchemaGuard验证
            validation = await self.schema_guard.validate_and_repair(
                storyboard_data, SchemaType.STORYBOARD
            )

            if validation.repaired_data:
                storyboard_data = validation.repaired_data

            # 保存当前分镜
            self.current_storyboard = storyboard_data

            # 生成友好的响应
            panels_count = len(storyboard_data.get("panels", []))
            characters = ", ".join([c.get("name", "未知") for c in storyboard_data.get("characters", [])])
            scenes = ", ".join([s.get("name", "未知") for s in storyboard_data.get("scenes", [])])

            response_text = f"""✅ 已生成 {panels_count} 格分镜！

📖 **{storyboard_data.get('title', '未命名故事')}**

🎭 **角色**: {characters or '无'}
🏠 **场景**: {scenes or '无'}
🎨 **风格**: {storyboard_data.get('style', '默认风格')}

---

**分镜预览**:
"""
            for panel in storyboard_data.get("panels", [])[:4]:
                pn = panel.get("panel_number", "?")
                desc = panel.get("description", "无描述")[:80]
                response_text += f"\n**第{pn}格**: {desc}"
                if panel.get("dialogue"):
                    for d in panel["dialogue"][:1]:
                        response_text += f"\n  💬 {d.get('speaker', '?')}: \"{d.get('text', '')}\"" 

            response_text += "\n\n---\n您可以说:\n- \"把第X格改成...\" 修改分镜\n- \"渲染所有分镜\" 开始生成图片\n- \"创建角色 [名字]\" 生成角色定妆照"

            yield {
                "type": "storyboard_created",
                "storyboard": storyboard_data,
            }
            
            yield {
                "type": "message",
                "content": response_text,
            }

        except Exception as e:
            logger.error(f"Failed to create storyboard: {e}", exc_info=True)
            yield {
                "type": "message",
                "content": f"抱歉，生成分镜时遇到问题：{str(e)}\n\n请重新描述您的故事。",
            }

    async def _modify_storyboard(
        self,
        user_message: str,
        context: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """修改分镜"""
        if not self.current_storyboard:
            yield {
                "type": "message",
                "content": "当前没有分镜可以修改。请先创建一个分镜。",
            }
            return

        yield {
            "type": "message",
            "content": "🎬 [导演模式]\n\n正在分析您的修改请求...",
        }

        # 使用PatchGenerator生成修改补丁
        patch_result = await self.patch_generator.generate_patch(
            user_instruction=user_message,
            current_state=self.current_storyboard,
            target_type=PatchTarget.STORYBOARD,
        )

        if not patch_result.success:
            yield {
                "type": "message",
                "content": f"抱歉，无法解析您的修改请求：{patch_result.error}",
            }
            return

        # 应用补丁
        modified_storyboard = self.patch_generator.apply_patches(
            self.current_storyboard, patch_result.patches
        )

        # 验证修改后的分镜
        validation = await self.schema_guard.validate_and_repair(
            modified_storyboard, SchemaType.STORYBOARD
        )

        if validation.repaired_data:
            modified_storyboard = validation.repaired_data

        # 记录补丁
        self.pending_patches.extend(patch_result.patches)

        # 更新当前分镜
        old_storyboard = self.current_storyboard
        self.current_storyboard = modified_storyboard

        # 生成响应
        changes_summary = "\n".join([f"- {p.reason}" for p in patch_result.patches])

        yield {
            "type": "storyboard_modified",
            "patches": [p.dict() for p in patch_result.patches],
            "storyboard": modified_storyboard,
        }

        yield {
            "type": "message",
            "content": f"""✅ 分镜已修改！

**修改内容**:
{changes_summary}

**摘要**: {patch_result.summary}

---
您可以继续修改或说\"确认分镜\"锁定当前版本。""",
        }

    async def _chat_response(
        self,
        user_message: str,
        context: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """一般对话响应"""
        response = await self._call_llm(
            user_message=user_message,
            system_prompt=self.get_system_prompt(),
            context=context,
        )
        
        yield {
            "type": "message",
            "content": response,
        }

    def get_current_storyboard(self) -> Optional[Dict[str, Any]]:
        """获取当前分镜"""
        return self.current_storyboard

    def get_pending_patches(self) -> List[Patch]:
        """获取待提交的补丁"""
        return self.pending_patches

    def clear_pending_patches(self) -> None:
        """清空待提交补丁"""
        self.pending_patches = []
