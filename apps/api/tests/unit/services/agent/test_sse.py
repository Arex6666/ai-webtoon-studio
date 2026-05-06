"""Tests for SSE event dispatcher + stream_response."""
import asyncio
import pytest

from app.services.agent.sse import EventDispatcher, stream_response


@pytest.mark.asyncio
async def test_register_emit_unregister():
    d = EventDispatcher()
    q = await d.register("c1")
    await d.emit("c1", "test", {"x": 1})
    etype, data = await q.get()
    assert etype == "test"
    assert data == {"x": 1}
    await d.unregister("c1", q)
    assert not await d.has_active_loop("c1")


@pytest.mark.asyncio
async def test_fanout_to_multiple_listeners():
    d = EventDispatcher()
    q1 = await d.register("c1")
    q2 = await d.register("c1")
    await d.emit("c1", "broadcast", {"k": "v"})
    a = await q1.get()
    b = await q2.get()
    assert a == b


@pytest.mark.asyncio
async def test_unregister_one_listener_does_not_affect_other():
    d = EventDispatcher()
    q1 = await d.register("c1")
    q2 = await d.register("c1")
    await d.unregister("c1", q1)
    await d.emit("c1", "still_works", {})
    etype, _ = await q2.get()
    assert etype == "still_works"


@pytest.mark.asyncio
async def test_emit_to_nonexistent_conversation_no_error():
    d = EventDispatcher()
    await d.emit("nonexistent", "ignored", {})  # should not raise


@pytest.mark.asyncio
async def test_stream_response_terminates_on_agent_done():
    q: asyncio.Queue = asyncio.Queue()
    await q.put(("conversation_started", {"conv_id": "c1"}))
    await q.put(("agent_done", {"reason": "stop"}))

    chunks = []
    async for chunk in stream_response("c1", q, heartbeat_interval=0.5):
        chunks.append(chunk)
    text = b"".join(chunks).decode("utf-8")
    assert "conversation_started" in text
    assert "agent_done" in text


@pytest.mark.asyncio
async def test_stream_response_terminates_on_unrecoverable_error():
    q: asyncio.Queue = asyncio.Queue()
    await q.put(("error", {"code": "INTERNAL_ERROR", "recoverable": False}))

    chunks = []
    async for chunk in stream_response("c1", q, heartbeat_interval=0.5):
        chunks.append(chunk)
    text = b"".join(chunks).decode("utf-8")
    assert "error" in text


@pytest.mark.asyncio
async def test_stream_response_emits_heartbeat_on_idle():
    q: asyncio.Queue = asyncio.Queue()
    chunks = []

    async def consume():
        async for chunk in stream_response("c1", q, heartbeat_interval=0.05):
            chunks.append(chunk)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.2)   # allow heartbeats to accumulate
    await q.put(("agent_done", {"reason": "stop"}))
    await asyncio.wait_for(task, timeout=2.0)
    text = b"".join(chunks).decode("utf-8")
    assert ": heartbeat" in text
    assert "agent_done" in text
