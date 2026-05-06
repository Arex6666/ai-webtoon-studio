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


from functools import lru_cache

from app.core.config import settings


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    """Return the configured singleton LLM provider."""
    p = settings.LLM_PROVIDER.lower()
    if p == "openai":
        from app.services.agent.providers.openai_compat import OpenAICompatibleProvider
        return OpenAICompatibleProvider(name="openai", base_url=settings.OPENAI_BASE_URL,
                                         api_key=settings.OPENAI_API_KEY or "",
                                         max_retries=settings.LLM_MAX_RETRIES)
    if p == "deepseek":
        from app.services.agent.providers.openai_compat import OpenAICompatibleProvider
        return OpenAICompatibleProvider(name="deepseek", base_url=settings.DEEPSEEK_BASE_URL,
                                         api_key=settings.DEEPSEEK_API_KEY or "",
                                         max_retries=settings.LLM_MAX_RETRIES)
    if p == "doubao":
        from app.services.agent.providers.openai_compat import OpenAICompatibleProvider
        return OpenAICompatibleProvider(
            name="doubao", base_url=settings.DOUBAO_BASE_URL,
            api_key=settings.DOUBAO_API_KEY or "",
            max_retries=settings.LLM_MAX_RETRIES,
        )
    if p == "tongyi":
        from app.services.agent.providers.openai_compat import OpenAICompatibleProvider
        return OpenAICompatibleProvider(
            name="tongyi", base_url=settings.TONGYI_BASE_URL,
            api_key=settings.TONGYI_API_KEY or "",
            max_retries=settings.LLM_MAX_RETRIES,
        )
    if p == "anthropic":
        from app.services.agent.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY or "",
                                  max_retries=settings.LLM_MAX_RETRIES)
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER}")
