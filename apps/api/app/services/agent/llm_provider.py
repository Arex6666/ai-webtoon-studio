"""LLMProvider abstract base + factory.

Provider implementations live in app/services/agent/providers/.
Configured by settings.LLM_PROVIDER; instantiated via get_llm_provider().
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator

from app.services.agent.llm_types import LLMMessage, StreamChunk
from app.services.agent.tool_registry import ToolDefinition


class LLMProviderError(Exception):
    """Raised after retries are exhausted."""


class LLMProvider(ABC):
    @abstractmethod
    async def stream(
        self,
        system: str,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        cache_hint: bool = True,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat-completion request as StreamChunks.

        Implementations must:
        - Translate LLMMessage list -> provider's message format
        - Translate tools -> provider's tools schema
        - Reassemble streamed tool-call argument fragments -> complete JSON dict
        - Honor cache_hint (Anthropic: emit cache_control on history block)
        - Retry on 429 / 5xx / network with exponential backoff (1s, 2s, 4s, 8s)
        - Raise LLMProviderError after 3 retries
        """
        raise NotImplementedError
        if False:  # pragma: no cover - make this a generator for type-checker
            yield

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def supports_tools(self) -> bool: ...

    @property
    @abstractmethod
    def supports_streaming_tool_calls(self) -> bool: ...
