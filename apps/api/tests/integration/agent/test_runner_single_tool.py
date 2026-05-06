"""End-to-end: agent loop with one read-only tool call."""
import pytest
import uuid

from app.services.agent.llm_types import StreamChunk, ToolCallSpec
from app.services.agent.runner import AgentRunner
from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY
from app.services.agent.sse import DISPATCHER
from tests.integration.agent.conftest import ScriptedProvider


@pytest.mark.asyncio
async def test_runner_executes_one_tool_then_stops(db_session, monkeypatch):
    # Setup: register a fake fast read-only tool
    handler_called = []

    async def fake_handler(args, context, db, tracer):
        handler_called.append(args)
        return {"echo": args.get("input")}

    fake_tool = ToolDefinition(
        name="echo", description="echo back",
        json_schema={"type": "object", "properties": {"input": {"type": "string"}}},
        handler=fake_handler, requires_context=("project_id",),
        expected_duration="fast", read_only=True,
    )
    TOOL_REGISTRY.clear()
    TOOL_REGISTRY.register(fake_tool)

    # Scripted LLM: step 1 calls echo, step 2 stops without tools
    provider = ScriptedProvider([
        [
            StreamChunk(type="content_delta", delta="Calling echo..."),
            StreamChunk(type="tool_call_done", tool_call_index=0,
                        tool_call=ToolCallSpec(id="c1", name="echo", arguments={"input": "hi"})),
            StreamChunk(type="stop", stop_reason="tool_calls"),
        ],
        [
            StreamChunk(type="content_delta", delta="Done!"),
            StreamChunk(type="stop", stop_reason="stop"),
        ],
    ])

    # Create conversation
    from app.models.conversation import Conversation
    conv_id = str(uuid.uuid4())
    db_session.add(Conversation(id=conv_id, project_id="p1", title="t"))
    db_session.commit()

    # Build runner with mocked provider
    monkeypatch.setattr("app.services.agent.runner.get_llm_provider", lambda: provider)
    runner = AgentRunner(db_session)
    runner.provider = provider   # belt-and-suspenders

    # Register listener BEFORE run so events are captured
    listener_q = await DISPATCHER.register(conv_id)

    await runner.run(conv_id, "hi", {"project_id": "p1"}, {"max_steps": 5})

    # Drain events
    events = []
    while not listener_q.empty():
        events.append(listener_q.get_nowait())
    types = [e[0] for e in events]
    assert "conversation_started" in types
    assert "tool_call" in types
    assert "tool_result" in types
    assert "agent_done" in types
    assert handler_called == [{"input": "hi"}]
    # Final agent_done should be reason=stop
    done_event = [e for e in events if e[0] == "agent_done"][-1]
    assert done_event[1]["reason"] == "stop"
