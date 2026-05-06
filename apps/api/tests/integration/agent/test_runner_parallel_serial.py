"""End-to-end: parallel read-only tools + serial write tool in same step."""
import asyncio
import pytest
import uuid

from app.services.agent.llm_types import StreamChunk, ToolCallSpec
from app.services.agent.runner import AgentRunner
from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY
from app.services.agent.sse import DISPATCHER
from tests.integration.agent.conftest import ScriptedProvider


@pytest.mark.asyncio
async def test_read_only_tools_run_concurrently(db_session, monkeypatch):
    order = []

    async def make_handler(tag, sleep_s):
        async def h(args, context, db, tracer):
            order.append(f"{tag}-start")
            await asyncio.sleep(sleep_s)
            order.append(f"{tag}-end")
            return {"tag": tag}
        return h

    h_a = await make_handler("a", 0.05)
    h_b = await make_handler("b", 0.05)
    h_w = await make_handler("write", 0.05)

    TOOL_REGISTRY.clear()
    TOOL_REGISTRY.register(ToolDefinition("read_a", "", {}, h_a, requires_context=(), read_only=True))
    TOOL_REGISTRY.register(ToolDefinition("read_b", "", {}, h_b, requires_context=(), read_only=True))
    TOOL_REGISTRY.register(ToolDefinition("write_w", "", {}, h_w, requires_context=(), read_only=False))

    provider = ScriptedProvider([
        [
            StreamChunk(type="tool_call_done", tool_call_index=0,
                        tool_call=ToolCallSpec(id="1", name="read_a", arguments={})),
            StreamChunk(type="tool_call_done", tool_call_index=1,
                        tool_call=ToolCallSpec(id="2", name="read_b", arguments={})),
            StreamChunk(type="tool_call_done", tool_call_index=2,
                        tool_call=ToolCallSpec(id="3", name="write_w", arguments={})),
            StreamChunk(type="stop", stop_reason="tool_calls"),
        ],
        [StreamChunk(type="stop", stop_reason="stop")],
    ])

    from app.models.conversation import Conversation
    conv_id = str(uuid.uuid4())
    db_session.add(Conversation(id=conv_id, project_id="p1", title="t"))
    db_session.commit()

    monkeypatch.setattr("app.services.agent.runner.get_llm_provider", lambda: provider)
    runner = AgentRunner(db_session)
    runner.provider = provider

    await DISPATCHER.register(conv_id)
    await runner.run(conv_id, "go", {}, {"max_steps": 3})

    # Read tools should overlap; write should run after both reads complete
    a_start = order.index("a-start")
    b_start = order.index("b-start")
    a_end = order.index("a-end")
    b_end = order.index("b-end")
    write_start = order.index("write-start")

    assert a_start < b_end and b_start < a_end, "read tools must overlap (parallel)"
    assert write_start > max(a_end, b_end), "write tool must run after all reads finish"
