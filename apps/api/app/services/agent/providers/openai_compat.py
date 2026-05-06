"""OpenAI-compatible streaming provider.

Used for: openai, deepseek, doubao, tongyi (all expose chat.completions with tool calls).
Differences are URL + key only; protocol is identical.
"""
import asyncio
import json
import logging
from typing import AsyncIterator

from openai import AsyncOpenAI

from app.services.agent.llm_provider import LLMProvider, LLMProviderError
from app.services.agent.llm_types import LLMMessage, StreamChunk, ToolCallSpec
from app.services.agent.tool_registry import ToolDefinition

_log = logging.getLogger(__name__)


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, *, name: str, base_url: str | None, api_key: str, max_retries: int = 3):
        self._name = name
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self._max_retries = max_retries

    @property
    def name(self) -> str: return self._name

    @property
    def supports_tools(self) -> bool: return True

    @property
    def supports_streaming_tool_calls(self) -> bool: return True

    async def stream(
        self, system, messages, tools, model,
        max_tokens=4096, temperature=0.7, cache_hint=True,
    ) -> AsyncIterator[StreamChunk]:
        msg_list = self._encode_messages(system, messages)
        tool_list = self._encode_tools(tools) if tools else None

        attempt = 0
        while True:
            try:
                async for chunk in self._stream_once(model, msg_list, tool_list, max_tokens, temperature):
                    yield chunk
                return
            except Exception as e:
                attempt += 1
                if attempt > self._max_retries or not self._should_retry(e):
                    raise LLMProviderError(f"{self._name} failed after {attempt} attempts: {e}") from e
                wait = 2 ** (attempt - 1)
                _log.warning("%s LLM call failed (attempt %d): %s — retrying in %ds", self._name, attempt, e, wait)
                await asyncio.sleep(wait)

    async def _stream_once(self, model, msg_list, tool_list, max_tokens, temperature):
        kwargs = dict(
            model=model,
            messages=msg_list,
            stream=True,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if tool_list:
            kwargs["tools"] = tool_list

        # Reassemble streamed tool-call argument fragments
        tc_buffer: dict[int, dict] = {}    # tool_call_index → {"id", "name", "arguments_buf"}

        async for chunk in await self._client.chat.completions.create(**kwargs):
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            finish_reason = chunk.choices[0].finish_reason

            if delta.content:
                yield StreamChunk(type="content_delta", delta=delta.content)

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    buf = tc_buffer.setdefault(idx, {"id": "", "name": "", "arguments_buf": ""})
                    if tc_delta.id:
                        buf["id"] = tc_delta.id
                        yield StreamChunk(type="tool_call_start", tool_call_index=idx)
                    if tc_delta.function and tc_delta.function.name:
                        buf["name"] = tc_delta.function.name
                    if tc_delta.function and tc_delta.function.arguments:
                        buf["arguments_buf"] += tc_delta.function.arguments
                        yield StreamChunk(type="tool_call_delta", tool_call_index=idx, delta=tc_delta.function.arguments)

            if finish_reason:
                # Emit any reassembled tool calls
                for idx in sorted(tc_buffer.keys()):
                    buf = tc_buffer[idx]
                    args = self._safe_json(buf["arguments_buf"])
                    yield StreamChunk(
                        type="tool_call_done",
                        tool_call_index=idx,
                        tool_call=ToolCallSpec(id=buf["id"], name=buf["name"], arguments=args),
                    )
                # Usage if reported
                usage = None
                if hasattr(chunk, "usage") and chunk.usage:
                    usage = {
                        "input_tokens": chunk.usage.prompt_tokens,
                        "output_tokens": chunk.usage.completion_tokens,
                    }
                yield StreamChunk(type="stop", stop_reason=finish_reason, usage=usage)

    def _encode_messages(self, system: str, messages: list[LLMMessage]) -> list[dict]:
        out: list[dict] = []
        if system:
            out.append({"role": "system", "content": system})
        for m in messages:
            entry: dict = {"role": m.role}
            if m.role == "tool":
                entry["tool_call_id"] = m.tool_call_id
                entry["name"] = m.name
                entry["content"] = m.content if isinstance(m.content, str) else json.dumps(m.content)
            elif m.role == "assistant" and m.tool_calls:
                entry["content"] = m.content or None
                entry["tool_calls"] = [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}}
                    for tc in m.tool_calls
                ]
            else:
                entry["content"] = m.content
            out.append(entry)
        return out

    def _encode_tools(self, tools: list[ToolDefinition]) -> list[dict]:
        return [
            {"type": "function", "function": {
                "name": t.name, "description": t.description, "parameters": t.json_schema,
            }}
            for t in tools
        ]

    @staticmethod
    def _safe_json(s: str) -> dict:
        try:
            return json.loads(s) if s else {}
        except json.JSONDecodeError:
            return {"__raw_arguments__": s}

    @staticmethod
    def _should_retry(e: Exception) -> bool:
        msg = str(e).lower()
        if "rate" in msg or "429" in msg or "5" in msg[:3]:
            return True
        return "timeout" in msg or "connection" in msg or "network" in msg
