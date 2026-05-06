"""Smoke tests for LLM-agnostic types."""
from app.services.agent.llm_types import ToolCallSpec, LLMMessage, StreamChunk


def test_dataclasses_construct():
    tc = ToolCallSpec(id="x", name="render", arguments={"a": 1})
    msg = LLMMessage(role="assistant", content="ok", tool_calls=[tc])
    assert msg.tool_calls[0].name == "render"
    chunk = StreamChunk(type="content_delta", delta="hello")
    assert chunk.delta == "hello"


def test_llm_message_default_content():
    m = LLMMessage(role="user")
    assert m.content == ""
    assert m.tool_calls is None


def test_tool_call_spec_is_frozen():
    import pytest
    tc = ToolCallSpec(id="x", name="y", arguments={})
    with pytest.raises(Exception):
        tc.id = "z"
