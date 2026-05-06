"""SSE event distribution — per-conversation listener fanout.

Agent loop runs as a background asyncio task and emits events to a per-conversation
event dispatcher. Each SSE HTTP connection registers a listener queue; the
dispatcher fans events to all listeners.

Disconnect of one listener does not stop the loop or other listeners.
"""
import asyncio
import json
import logging
from typing import AsyncIterator

logger = logging.getLogger(__name__)


class EventDispatcher:
    def __init__(self):
        self._listeners: dict[str, list[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def register(self, conversation_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        async with self._lock:
            self._listeners.setdefault(conversation_id, []).append(q)
        return q

    async def unregister(self, conversation_id: str, q: asyncio.Queue) -> None:
        async with self._lock:
            lst = self._listeners.get(conversation_id)
            if not lst:
                return
            try:
                lst.remove(q)
            except ValueError:
                pass
            if not lst:
                self._listeners.pop(conversation_id, None)

    async def emit(self, conversation_id: str, event_type: str, data: dict) -> None:
        async with self._lock:
            queues = list(self._listeners.get(conversation_id, []))
        for q in queues:
            try:
                q.put_nowait((event_type, data))
            except asyncio.QueueFull:
                logger.error("SSE listener queue full for conv %s — dropping listener", conversation_id)
                # Drop the saturated listener; HTTP handler will see queue close on next get
                await self.unregister(conversation_id, q)

    async def has_active_loop(self, conversation_id: str) -> bool:
        async with self._lock:
            return conversation_id in self._listeners and len(self._listeners[conversation_id]) > 0


DISPATCHER = EventDispatcher()


async def stream_response(
    conversation_id: str,
    q: asyncio.Queue,
    heartbeat_interval: float = 15.0,
) -> AsyncIterator[bytes]:
    """Convert events from a listener queue into SSE wire bytes.

    Includes periodic heartbeat comments to keep proxies alive.
    Stream ends when an `agent_done` or non-recoverable `error` event passes through.
    """
    event_id = 0
    while True:
        try:
            etype, data = await asyncio.wait_for(q.get(), timeout=heartbeat_interval)
        except asyncio.TimeoutError:
            yield b": heartbeat\n\n"
            continue

        event_id += 1
        payload = json.dumps(data, ensure_ascii=False, default=str)
        yield f"event: {etype}\nid: {event_id}\ndata: {payload}\n\n".encode("utf-8")

        if etype == "agent_done":
            return
        if etype == "error" and not data.get("recoverable", True):
            return
