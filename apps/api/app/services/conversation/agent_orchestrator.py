"""
AgentOrchestrator - 智能体编排器
协调多个智能体处理用户消息
"""
import logging
from typing import Dict, Any, Optional, AsyncGenerator
from sqlalchemy.orm import Session

from app.services.conversation.intent_router import IntentRouter
from app.services.conversation.tool_registry import ToolRegistry
from app.services.conversation.conversation_service import ConversationService
from app.schemas.conversation import (
    IntentAnalysisResult,
    ConversationMessageCreate,
    ToolCall,
    ToolResult,
)

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """智能体编排器"""

    def __init__(self, db: Session):
        self.db = db
        self.intent_router = IntentRouter()
        self.tool_registry = ToolRegistry()
        self.conversation_service = ConversationService(db)
        self.agents = {}  # 智能体实例缓存
        
        # 绑定工具处理函数
        self.tool_registry.bind_handlers(db)

    def register_agent(self, agent_name: str, agent_instance: Any):
        """注册智能体"""
        self.agents[agent_name] = agent_instance
        logger.info(f"Registered agent: {agent_name}")

    def get_agent(self, agent_name: str) -> Optional[Any]:
        """获取智能体实例"""
        return self.agents.get(agent_name)

    async def process_message(
        self,
        conversation_id: str,
        user_message: str,
        streaming: bool = True,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        处理用户消息

        Args:
            conversation_id: 对话ID
            user_message: 用户消息
            streaming: 是否流式响应

        Yields:
            响应事件
        """
        try:
            # 1. 获取对话上下文
            context = self.conversation_service.get_context(conversation_id)

            # 2. 分析意图
            intent_result = await self.intent_router.analyze_intent(user_message, context)
            logger.info(
                f"Intent analysis: {intent_result.primary_intent} (confidence: {intent_result.confidence})"
            )

            # 3. 保存用户消息
            user_msg = self.conversation_service.add_message(
                ConversationMessageCreate(
                    conversation_id=conversation_id,
                    role="user",
                    content=user_message,
                    intent=intent_result.primary_intent,
                    entities_json=intent_result.entities,
                )
            )

            # 4. 路由到对应的智能体
            agent_name = self.intent_router.route_to_agent(intent_result.primary_intent)
            agent = self.get_agent(agent_name)

            if not agent:
                logger.error(f"Agent not found: {agent_name}")
                yield {
                    "type": "error",
                    "error": f"智能体未找到: {agent_name}",
                }
                return

            # 5. 智能体处理消息
            assistant_message_id = None
            assistant_content = ""
            tool_calls = []
            tool_results = []

            async for event in agent.process(
                user_message=user_message,
                intent=intent_result,
                context=context,
                streaming=streaming,
            ):
                event_type = event.get("type")

                # 流式响应块
                if event_type == "message_chunk":
                    chunk = event.get("chunk", "")
                    assistant_content += chunk
                    yield {
                        "type": "assistant_message_chunk",
                        "message_id": assistant_message_id or "temp",
                        "chunk": chunk,
                        "is_final": False,
                    }

                # 完整消息
                elif event_type == "message":
                    assistant_content = event.get("content", "")
                    yield {
                        "type": "assistant_message",
                        "content": assistant_content,
                        "intent": intent_result.primary_intent,
                        "entities": intent_result.entities,
                    }

                # 工具调用
                elif event_type == "tool_call":
                    tool_call = event.get("tool_call")
                    tool_calls.append(tool_call)
                    yield {
                        "type": "tool_call",
                        "tool_name": tool_call.get("tool_name"),
                        "parameters": tool_call.get("parameters"),
                    }

                    # 执行工具
                    tool_result = await self._execute_tool(
                        conversation_id=conversation_id,
                        message_id=user_msg.id,
                        tool_call=tool_call,
                    )
                    tool_results.append(tool_result)

                    # 发送工具结果
                    yield {
                        "type": "tool_result",
                        "tool_name": tool_result.get("tool_name"),
                        "success": tool_result.get("success"),
                        "result": tool_result.get("result"),
                    }

                # 动作通知
                elif event_type in ["action_started", "action_progress", "action_completed", "action_failed"]:
                    yield event

            # 6. 保存助手消息
            if assistant_content:
                assistant_msg = self.conversation_service.add_message(
                    ConversationMessageCreate(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=assistant_content,
                        intent=intent_result.primary_intent,
                        entities_json=intent_result.entities,
                        tool_calls_json=tool_calls,
                        tool_results_json=tool_results,
                        model_used=agent.model_name if hasattr(agent, "model_name") else None,
                        tokens_used=0,  # TODO: 计算实际token使用
                    )
                )
                assistant_message_id = assistant_msg.id

            # 7. 更新对话上下文
            updated_context = context.get("context_data", {})
            updated_context.update(intent_result.entities)
            self.conversation_service.update_context(
                conversation_id=conversation_id,
                context_data=updated_context,
                current_intent=intent_result.primary_intent,
            )

            # 8. 发送完成信号
            yield {
                "type": "message_complete",
                "message_id": assistant_message_id,
            }

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            yield {
                "type": "error",
                "error": str(e),
            }

    async def _execute_tool(
        self,
        conversation_id: str,
        message_id: str,
        tool_call: Dict[str, Any],
    ) -> Dict[str, Any]:
        """执行工具调用"""
        tool_name = tool_call.get("tool_name")
        parameters = tool_call.get("parameters", {})

        try:
            # 创建动作记录
            from app.schemas.conversation import ConversationActionCreate

            action = self.conversation_service.create_action(
                ConversationActionCreate(
                    conversation_id=conversation_id,
                    message_id=message_id,
                    action_type=tool_name,
                    action_params_json=parameters,
                )
            )

            # 执行工具
            result = await self.tool_registry.execute_tool(
                tool_name=tool_name,
                parameters=parameters,
            )

            # 更新动作状态
            self.conversation_service.update_action_status(
                action_id=action.id,
                status="completed" if result.get("success") else "failed",
                result_json=result.get("result"),
                error_json={"error": result.get("error")} if not result.get("success") else None,
            )

            return {
                "tool_name": tool_name,
                "success": result.get("success"),
                "result": result.get("result"),
                "error": result.get("error"),
            }

        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name}, error: {e}")
            return {
                "tool_name": tool_name,
                "success": False,
                "error": str(e),
            }

    async def generate_response(
        self,
        conversation_id: str,
        intent: str,
        entities: Dict[str, Any],
        tool_results: list,
    ) -> str:
        """
        生成最终响应

        Args:
            conversation_id: 对话ID
            intent: 意图
            entities: 实体
            tool_results: 工具执行结果

        Returns:
            响应文本
        """
        # 根据意图和工具结果生成响应
        if not tool_results:
            return "我已经理解了您的需求。"

        # 构建响应
        response_parts = []
        for result in tool_results:
            if result.get("success"):
                response_parts.append(f"✓ {result.get('tool_name')} 执行成功")
            else:
                response_parts.append(f"✗ {result.get('tool_name')} 执行失败: {result.get('error')}")

        return "\n".join(response_parts)
