"""End-to-end: cancellation flag interrupts loop at step boundary."""
import pytest
import uuid

from app.services.agent.llm_types import StreamChunk
from app.services.agent.runner import AgentRunner
from app.services.agent.cancellation import request_cancel
from app.services.agent.sse import DISPATCHER
from tests.integration.agent.conftest import ScriptedProvider


@pytest.mark.asyncio
async def test_cancel_flag_stops_loop_at_step_boundary(db_session, monkeypatch):
    # Use fakeredis for cancellation backend
    import fakeredis.aioredis
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    from app.services.agent import cancellation

    async def _r(): return fake
    monkeypatch.setattr(cancellation, "_get_redis", _r)

    provider = ScriptedProvider([
        [StreamChunk(type="content_delta", delta="hi"), StreamChunk(type="stop", stop_reason="stop")],
    ])

    from app.models.conversation import Conversation
    conv_id = str(uuid.uuid4())
    db_session.add(Conversation(id=conv_id, project_id="p1", title="t"))
    db_session.commit()

    # Set cancel flag BEFORE the loop runs
    await request_cancel(conv_id)

    monkeypatch.setattr("app.services.agent.runner.get_llm_provider", lambda: provider)
    # Note: runner clears cancel flag at the start of run() — we need to set it AFTER user message persisted but BEFORE step 0.
    # Simplest: monkeypatch clear_cancel to no-op so our pre-set flag stands.
    async def _noop_clear(_):
        pass
    monkeypatch.setattr("app.services.agent.runner.clear_cancel", _noop_clear)

    # Re-set flag after monkeypatch (in case order matters)
    await request_cancel(conv_id)

    runner = AgentRunner(db_session)
    runner.provider = provider
    listener_q = await DISPATCHER.register(conv_id)
    await runner.run(conv_id, "msg", {}, {"max_steps": 5})

    events = []
    while not listener_q.empty():
        events.append(listener_q.get_nowait())
    done_events = [e for e in events if e[0] == "agent_done"]
    assert done_events
    assert done_events[-1][1]["reason"] == "user_canceled"
