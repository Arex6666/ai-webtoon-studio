"""
IntentRouter - 意图路由器
使用 LLM 分析用户消息的意图，并路由到相应的智能体
"""
import logging
import json
from typing import Dict, Any, List, Optional

from app.services.brain.standard_llm import StandardLLMService
from app.schemas.conversation import IntentAnalysisResult

logger = logging.getLogger(__name__)


# 意图分析的系统提示词
INTENT_ANALYSIS_PROMPT = """你是一个意图分析专家。分析用户消息并识别意图类型。

可能的意图类型:
- script: 创建/修改剧本和分镜（例如："创建一个四格漫画"、"修改第二格的对话"）
- asset: 创建/查询角色、场景、道具（例如："创建一个角色叫小明"、"查看所有场景"）
- render: 渲染分镜、查看进度（例如："渲染所有分镜"、"渲染进度如何"）
- qa: 质量分析、问题修复（例如："第二格的构图不好"、"分析质量问题"）
- general: 一般对话、帮助、问候（例如："你好"、"你能做什么"）

请分析用户消息，返回JSON格式:
{
  "primary_intent": "script",
  "secondary_intents": [],
  "entities": {
    "character_names": ["小明"],
    "scene_names": [],
    "panel_indices": []
  },
  "confidence": 0.95
}

注意:
1. primary_intent 是主要意图
2. secondary_intents 是次要意图（如果有多个意图）
3. entities 是提取的实体信息
4. confidence 是置信度 (0-1)
"""


class IntentRouter:
    """意图路由器"""

    def __init__(self):
        self.llm = StandardLLMService()

    async def analyze_intent(
        self, user_message: str, context: Optional[Dict[str, Any]] = None
    ) -> IntentAnalysisResult:
        """
        分析用户消息的意图

        Args:
            user_message: 用户消息
            context: 对话上下文（可选）

        Returns:
            IntentAnalysisResult
        """
        try:
            # 构建上下文信息
            context_info = ""
            if context and context.get("recent_messages"):
                recent = context["recent_messages"][-3:]  # 最近3条消息
                context_info = "\n\n最近的对话:\n"
                for msg in recent:
                    context_info += f"- {msg['role']}: {msg['content'][:100]}\n"

            # 构建提示词
            messages = [
                {"role": "system", "content": INTENT_ANALYSIS_PROMPT},
                {
                    "role": "user",
                    "content": f"用户消息: {user_message}{context_info}\n\n请分析意图并返回JSON。",
                },
            ]

            # 调用 LLM
            response = await self.llm._chat_completion(messages, response_format="json")

            # 解析响应
            result_data = json.loads(response)

            # 验证和规范化
            primary_intent = result_data.get("primary_intent", "general")
            if primary_intent not in ["script", "asset", "render", "qa", "general"]:
                logger.warning(f"Unknown intent: {primary_intent}, defaulting to 'general'")
                primary_intent = "general"

            return IntentAnalysisResult(
                primary_intent=primary_intent,
                secondary_intents=result_data.get("secondary_intents", []),
                entities=result_data.get("entities", {}),
                confidence=result_data.get("confidence", 0.0),
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse intent analysis response: {e}")
            # 降级：使用简单的关键词匹配
            return self._fallback_intent_analysis(user_message)

        except Exception as e:
            logger.error(f"Intent analysis failed: {e}")
            return self._fallback_intent_analysis(user_message)

    def _fallback_intent_analysis(self, user_message: str) -> IntentAnalysisResult:
        """降级方案：使用关键词匹配"""
        message_lower = user_message.lower()

        # 关键词映射
        intent_keywords = {
            "script": ["剧本", "故事", "分镜", "四格", "漫画", "情节", "对话"],
            "asset": ["角色", "场景", "道具", "创建", "人物", "背景"],
            "render": ["渲染", "生成", "画", "图片", "预览"],
            "qa": ["质量", "问题", "修复", "不好", "错误", "调整"],
        }

        # 匹配意图
        for intent, keywords in intent_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                return IntentAnalysisResult(
                    primary_intent=intent,
                    secondary_intents=[],
                    entities={},
                    confidence=0.6,
                )

        # 默认为 general
        return IntentAnalysisResult(
            primary_intent="general",
            secondary_intents=[],
            entities={},
            confidence=0.5,
        )

    def route_to_agent(self, intent: str) -> str:
        """
        根据意图路由到对应的智能体

        Args:
            intent: 意图类型

        Returns:
            智能体名称
        """
        agent_mapping = {
            "script": "script_agent",
            "asset": "asset_agent",
            "render": "rendering_agent",
            "qa": "qa_agent",
            "general": "general_agent",
        }

        return agent_mapping.get(intent, "general_agent")

    async def handle_multi_intent(
        self, intents: List[str], user_message: str, context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        处理多意图消息

        Args:
            intents: 意图列表
            user_message: 用户消息
            context: 上下文

        Returns:
            智能体响应列表
        """
        responses = []

        for intent in intents:
            agent_name = self.route_to_agent(intent)
            responses.append(
                {
                    "intent": intent,
                    "agent": agent_name,
                    "message": user_message,
                }
            )

        return responses
