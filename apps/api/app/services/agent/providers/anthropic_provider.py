"""Anthropic Claude provider with explicit cache_control."""
import asyncio
import json
import logging
from typing import AsyncIterator

from anthropic import AsyncAnthropic

from app.services.agent.llm_provider import LLMProvider, LLMProviderError
from app.services.agent.llm_types import LLMMessage, StreamChunk, ToolCallSpec
from app.services.agent.tool_registry import ToolDefinition

_log = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    def __init__(self, *, api_key: str, max_retries: int = 3):
        self._client = AsyncAnthropic(api_key=api_key)
        self._max_retries = max_retries

    @property
    def name(self) -> str: return "anthropic"

    @property
    def supports_tools(self) -> bool: return True

    @property
    def supports_streaming_tool_calls(self) -> bool: return True

    async def stream(
        self, system, messages, tools, model,
        max_tokens=4096, temperature=0.7, cache_hint=True,
    ) -> AsyncIterator[StreamChunk]:
        anthropic_msgs = self._encode_messages(messages, cache_hint)
        anthropic_tools = self._encode_tools(tools) if tools else None

        attempt = 0
        while True:
            try:
                async for chunk in self._stream_once(model, system, anthropic_msgs, anthropic_tools, max_tokens, temperature):
                    yield chunk
                return
            except Exception as e:
                attempt += 1
                if attempt > self._max_retries or not self._should_retry(e):
                    raise LLMProviderError(f"anthropic failed after {attempt} attempts: {e}") from e
                await asyncio.sleep(2 ** (attempt - 1))

    async def _stream_once(self, model, system, msgs, tools, max_tokens, temperature):
        kwargs = dict(model=model, system=system, messages=msgs, max_tokens=max_tokens, temperature=temperature)
        if tools:
            kwargs["tools"] = tools

        tc_buffer: dict[int, dict] = {}
        async with self._client.messages.stream(**kwargs) as stream:
            async for event in stream:
                etype = event.type
                if etype == "content_block_start" and getattr(event.content_block, "type", None) == "tool_use":
                    idx = event.index
                    tc_buffer[idx] = {
                        "id": event.content_block.id,
                        "name": event.content_block.name,
                        "arguments_buf": "",
                    }
                    yield StreamChunk(type="tool_call_start", tool_call_index=idx)
                elif etype == "content_block_delta":
                    d = event.delta
                    if d.type == "text_delta":
                        yield StreamChunk(type="content_delta", delta=d.text)
                    elif d.type == "input_json_delta":
                        idx = event.index
                        tc_buffer[idx]["arguments_buf"] += d.partial_json
                        yield StreamChunk(type="tool_call_delta", tool_call_index=idx, delta=d.partial_json)
                elif etype == "message_stop":
                    for idx in sorted(tc_buffer.keys()):
                        buf = tc_buffer[idx]
                        args = self._safe_json(buf["arguments_buf"])
                        yield StreamChunk(
                            type="tool_call_done", tool_call_index=idx,
                            tool_call=ToolCallSpec(id=buf["id"], name=buf["name"], arguments=args),
                        )
                    final = await stream.get_final_message()
                    usage = None
                    if final.usage:
                        usage = {
                            "input_tokens": final.usage.input_tokens,
                            "output_tokens": final.usage.output_tokens,
                            "cache_hit": getattr(final.usage, "cache_read_input_tokens", 0) > 0,
                        }
                    yield StreamChunk(type="stop", stop_reason=final.stop_reason, usage=usage)

    def _encode_messages(self, messages: list[LLMMessage], cache_hint: bool) -> list[dict]:
        out = []
        for i, m in enumerate(messages):
            if m.role == "tool":
                out.append({"role": "user", "content": [{
                    "type": "tool_result", "tool_use_id": m.tool_call_id,
                    "content": m.content if isinstance(m.content, str) else json.dumps(m.content),
                }]})
                continue
            if m.role == "assistant" and m.tool_calls:
                blocks = []
                if m.content:
                    blocks.append({"type": "text", "text": m.content})
                for tc in m.tool_calls:
                    blocks.append({"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments})
                out.append({"role": "assistant", "content": blocks})
                continue
            content = m.content if isinstance(m.content, str) else json.dumps(m.content)
            entry: dict = {"role": m.role, "content": content}
            # cache_hint: mark all messages except the last with cache_control
            if cache_hint and i < len(messages) - 1:
                entry["content"] = [{"type": "text", "text": content,
                                      "cache_control": {"type": "ephemeral"}}]
            out.append(entry)
        return out

    def _encode_tools(self, tools: list[ToolDefinition]) -> list[dict]:
        return [{"name": t.name, "description": t.description, "input_schema": t.json_schema}
                for t in tools]

    @staticmethod
    def _safe_json(s: str) -> dict:
        try:
            return json.loads(s) if s else {}
        except json.JSONDecodeError:
            return {"__raw_arguments__": s}

    @staticmethod
    def _should_retry(e: Exception) -> bool:
        msg = str(e).lower()
        return any(s in msg for s in ("rate", "429", "5", "timeout", "connection"))
