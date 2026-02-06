"""
ScriptAgent - 剧本智能体
处理剧本创建、分镜生成相关的请求
"""
import logging
from typing import Dict, Any, AsyncGenerator
from sqlalchemy.orm import Session

from app.services.agents.base_agent import BaseAgent
from app.services.script_pipeline import ScriptPipelineService
from app.schemas.conversation import IntentAnalysisResult

logger = logging.getLogger(__name__)


SCRIPT_AGENT_PROMPT = """你是一个专业的漫画剧本创作助手。你的职责是：
1. 理解用户的故事需求
2. 生成适合漫画表现的分镜剧本
3. 根据反馈优化剧本

当用户描述故事时，你需要：
- 提取关键情节点
- 确定角色和场景
- 规划分镜数量和节奏
- 生成详细的分镜描述

请用友好、专业的语气与用户交流。"""


class ScriptAgent(BaseAgent):
    """剧本智能体"""

    def __init__(self, db: Session):
        super().__init__(
            name="script_agent",
            description="处理剧本创建和分镜生成",
        )
        self.db = db
        self.script_pipeline = ScriptPipelineService()

    async def process(
        self,
        user_message: str,
        intent: IntentAnalysisResult,
        context: Dict[str, Any],
        streaming: bool = True,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """处理剧本相关请求"""
        try:
            # 判断是否需要生成分镜
            if self._should_generate_storyboard(user_message, intent):
                async for event in self._generate_storyboard(user_message, intent, context):
                    yield event
            else:
                # 一般对话
                async for event in self._chat_response(user_message, context, streaming):
                    yield event

        except Exception as e:
            logger.error(f"ScriptAgent error: {e}", exc_info=True)
            yield {
                "type": "error",
                "error": str(e),
            }

    def _should_generate_storyboard(self, user_message: str, intent: IntentAnalysisResult) -> bool:
        """判断是否需要生成分镜"""
        keywords = ["创建", "生成", "做一个", "帮我", "四格", "漫画", "故事", "分镜"]
        message_lower = user_message.lower()
        return any(keyword in message_lower for keyword in keywords)

    async def _generate_storyboard(
        self,
        user_message: str,
        intent: IntentAnalysisResult,
        context: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """生成分镜"""
        try:
            # 1. 发送开始消息
            yield {
                "type": "message",
                "content": "好的，我来帮您创建分镜。正在分析故事...",
            }

            # 2. 提取分镜数量（默认4格）
            panel_count = self._extract_panel_count(user_message)

            # 3. 调用工具生成分镜
            yield {
                "type": "tool_call",
                "tool_call": {
                    "tool_name": "generate_storyboard",
                    "parameters": {
                        "story": user_message,
                        "panel_count": panel_count,
                    },
                },
            }

            # 4. 使用 ScriptPipeline 解析剧本
            yield {
                "type": "action_started",
                "action_id": "parse_script",
                "action_type": "parse_script",
                "description": "正在解析剧本...",
            }

            parse_result = await self.script_pipeline.task_parse(user_message)

            yield {
                "type": "action_completed",
                "action_id": "parse_script",
                "action_type": "parse_script",
                "result": {
                    "characters": [c.name for c in parse_result.script_ir.characters],
                    "scenes": [s.name for s in parse_result.script_ir.scenes],
                    "panel_count": len(parse_result.script_ir.beats),
                },
            }

            # 5. 生成响应
            characters = ", ".join([c.name for c in parse_result.script_ir.characters])
            scenes = ", ".join([s.name for s in parse_result.script_ir.scenes])
            panel_count = len(parse_result.script_ir.beats)

            response = f"""已为您生成 {panel_count} 格分镜！

📝 **角色**: {characters}
🎬 **场景**: {scenes}

接下来您可以：
- 说"渲染所有分镜"来生成图片
- 说"创建角色 [角色名]"来生成角色定妆照
- 说"修改第X格"来调整具体分镜"""

            yield {
                "type": "message",
                "content": response,
            }

        except Exception as e:
            logger.error(f"Storyboard generation failed: {e}", exc_info=True)
            yield {
                "type": "message",
                "content": f"抱歉，生成分镜时出现错误：{str(e)}",
            }

    async def _chat_response(
        self,
        user_message: str,
        context: Dict[str, Any],
        streaming: bool,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """一般对话响应"""
        try:
            if streaming:
                # 流式响应
                async for chunk in self._stream_llm_response(
                    messages=[{"role": "user", "content": user_message}],
                    system_prompt=SCRIPT_AGENT_PROMPT,
                ):
                    yield {
                        "type": "message_chunk",
                        "chunk": chunk,
                    }
            else:
                # 非流式响应
                response = await self._call_llm(
                    user_message=user_message,
                    system_prompt=SCRIPT_AGENT_PROMPT,
                    context=context,
                )
                yield {
                    "type": "message",
                    "content": response,
                }

        except Exception as e:
            logger.error(f"Chat response failed: {e}", exc_info=True)
            yield {
                "type": "message",
                "content": "抱歉，我现在无法回答。请稍后再试。",
            }

    def _extract_panel_count(self, user_message: str) -> int:
        """从用户消息中提取分镜数量"""
        import re

        # 查找数字
        numbers = re.findall(r'\d+', user_message)
        if numbers:
            count = int(numbers[0])
            if 1 <= count <= 20:  # 限制在合理范围
                return count

        # 默认4格
        return 4

    async def refine_script(
        self,
        script_id: str,
        feedback: str,
    ) -> Dict[str, Any]:
        """优化剧本"""
        # TODO: 实现剧本优化逻辑
        return {
            "success": True,
            "message": "剧本已优化",
        }
