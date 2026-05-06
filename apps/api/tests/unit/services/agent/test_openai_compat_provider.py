"""Tests for OpenAICompatibleProvider — encoding only (real streaming exercised in integration)."""
import json

from app.services.agent.providers.openai_compat import OpenAICompatibleProvider
from app.services.agent.llm_types import LLMMessage, ToolCallSpec
from app.services.agent.tool_registry import ToolDefinition


def _provider() -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(name="test", base_url="http://x", api_key="k")


def test_encode_messages_user_only():
    p = _provider()
    out = p._encode_messages("sys", [LLMMessage(role="user", content="hi")])
    assert out == [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}]


def test_encode_messages_assistant_with_tool_calls():
    p = _provider()
    tc = ToolCallSpec(id="c1", name="render", arguments={"x": 1})
    msg = LLMMessage(role="assistant", content="", tool_calls=[tc])
    out = p._encode_messages("", [msg])
    assert out[0]["tool_calls"][0]["id"] == "c1"
    assert json.loads(out[0]["tool_calls"][0]["function"]["arguments"]) == {"x": 1}


def test_encode_messages_tool_role():
    p = _provider()
    msg = LLMMessage(role="tool", content='{"ok": 1}', tool_call_id="c1", name="render")
    out = p._encode_messages("", [msg])
    assert out[0]["role"] == "tool"
    assert out[0]["tool_call_id"] == "c1"


def test_encode_tools():
    p = _provider()
    async def h(): return None
    t = ToolDefinition(name="x", description="d", json_schema={"type": "object"}, handler=h)
    out = p._encode_tools([t])
    assert out == [{"type": "function", "function": {"name": "x", "description": "d", "parameters": {"type": "object"}}}]


def test_safe_json_handles_malformed():
    p = _provider()
    assert p._safe_json("") == {}
    assert p._safe_json('{"a": 1}') == {"a": 1}
    assert p._safe_json("not json").get("__raw_arguments__") == "not json"


def test_should_retry_on_rate_limit():
    p = _provider()
    assert p._should_retry(Exception("HTTP 429 rate limit"))
    assert p._should_retry(Exception("connection reset"))
    assert not p._should_retry(Exception("invalid request"))
