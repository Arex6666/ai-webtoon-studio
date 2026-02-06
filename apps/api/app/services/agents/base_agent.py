"""
Base Agent - 基础智能体类
所有专业智能体的基类
"""
import logging
from typing import Dict, Any, AsyncGenerator, Optional
from abc import ABC, abstractmethod

from app.services.brain.standard_llm import StandardLLMService
from app.schemas.conversation import IntentAnalysisResult

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """基础智能体类"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.llm = StandardLLMService()
        self.model_name = self.llm.model

    @abstractmethod
    async def process(
        self,
        user_message: str,
        intent: IntentAnalysisResult,
        context: Dict[str, Any],
        streaming: bool = True,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        处理用户消息

        Args:
            user_message: 用户消息
            intent: 意图分析结果
            context: 对话上下文
            streaming: 是否流式响应

        Yields:
            响应事件
        """
        pass

    async def _stream_llm_response(
        self,
        messages: list,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式调用 LLM

        Args:
            messages: 消息列表
            system_prompt: 系统提示词

        Yields:
            响应块
        """
        # 添加系统提示词
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        try:
            # 使用真正的流式响应
            async for chunk in self.llm._stream_chat_completion(messages):
                yield chunk
        except Exception as e:
            logger.warning(f"Stream failed, falling back to non-streaming: {e}")
            # 降级到非流式，模拟流式输出
            response = await self.llm._chat_completion(messages)
            chunk_size = 10
            for i in range(0, len(response), chunk_size):
                chunk = response[i : i + chunk_size]
                yield chunk

    def _build_context_messages(self, context: Dict[str, Any], max_messages: int = 5) -> list:
        """
        构建上下文消息列表

        Args:
            context: 对话上下文
            max_messages: 最大消息数

        Returns:
            消息列表
        """
        messages = []
        recent_messages = context.get("recent_messages", [])[-max_messages:]

        for msg in recent_messages:
            messages.append(
                {
                    "role": msg["role"],
                    "content": msg["content"],
                }
            )

        return messages

    def _extract_entities_from_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """从上下文中提取实体"""
        return context.get("context_data", {})

    async def _call_llm(
        self,
        user_message: str,
        system_prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        调用 LLM

        Args:
            user_message: 用户消息
            system_prompt: 系统提示词
            context: 上下文

        Returns:
            LLM 响应
        """
        messages = []

        # 添加上下文消息
        if context:
            messages.extend(self._build_context_messages(context))

        # 添加当前用户消息
        messages.append({"role": "user", "content": user_message})

        # 添加系统提示词并调用
        full_messages = [{"role": "system", "content": system_prompt}] + messages

        return await self.llm._chat_completion(full_messages)
