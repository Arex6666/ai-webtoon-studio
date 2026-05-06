"""Encoding tests for AnthropicProvider."""
import json

from app.services.agent.providers.anthropic_provider import AnthropicProvider
from app.services.agent.llm_types import LLMMessage, ToolCallSpec
from app.services.agent.tool_registry import ToolDefinition


def _p(): return AnthropicProvider(api_key="x")


def test_tool_role_becomes_tool_result_block():
    p = _p()
    msg = LLMMessage(role="tool", content='{"ok": 1}', tool_call_id="c1", name="render")
    out = p._encode_messages([msg], cache_hint=False)
    assert out[0]["role"] == "user"
    assert out[0]["content"][0]["type"] == "tool_result"
    assert out[0]["content"][0]["tool_use_id"] == "c1"


def test_assistant_with_tool_calls_becomes_tool_use_block():
    p = _p()
    tc = ToolCallSpec(id="c1", name="render", arguments={"x": 1})
    msg = LLMMessage(role="assistant", content="ok", tool_calls=[tc])
    out = p._encode_messages([msg], cache_hint=False)
    blocks = out[0]["content"]
    assert blocks[0] == {"type": "text", "text": "ok"}
    assert blocks[1]["type"] == "tool_use"
    assert blocks[1]["id"] == "c1"
    assert blocks[1]["input"] == {"x": 1}


def test_cache_hint_wraps_all_but_last():
    p = _p()
    msgs = [
        LLMMessage(role="user", content="m1"),
        LLMMessage(role="assistant", content="m2"),
        LLMMessage(role="user", content="m3"),
    ]
    out = p._encode_messages(msgs, cache_hint=True)
    # First two have cache_control, last does not
    assert isinstance(out[0]["content"], list) and out[0]["content"][0]["cache_control"]["type"] == "ephemeral"
    assert isinstance(out[1]["content"], list) and out[1]["content"][0]["cache_control"]["type"] == "ephemeral"
    assert out[2]["content"] == "m3"


def test_encode_tools_uses_input_schema_field():
    p = _p()
    async def h(): return None
    t = ToolDefinition(name="x", description="d", json_schema={"type": "object"}, handler=h)
    out = p._encode_tools([t])
    assert out == [{"name": "x", "description": "d", "input_schema": {"type": "object"}}]
