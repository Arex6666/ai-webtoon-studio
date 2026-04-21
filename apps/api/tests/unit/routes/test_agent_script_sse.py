"""Integration tests for POST /api/v1/agent/episode/{n}/script/stream (SSE).

Task 9 — verifies the SSE streaming variant emits the expected event sequence:

1. Happy path: core returns an ``EpisodeScriptResponse`` -> stream emits at least
   one ``progress`` frame followed by a ``done`` frame carrying the serialized
   response.
2. Error path: core raises -> stream emits an ``error`` frame with the
   exception message (and does NOT emit a ``done`` frame).

The core coroutine ``_generate_episode_script_core`` is patched so the tests do
not hit the real LLM / card-writer path; they focus purely on the SSE framing.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def _make_request_body() -> dict:
    """Minimal valid EpisodeScriptRequest body (matches BaseModel in agent.py)."""
    return {
        "project_id": "proj-sse-test",
        "episode_number": 1,
        "outline_text": "Alice meets Bob on the rooftop at sunset.",
        "conversation_id": "conv-sse-1",
    }


def _fake_response():
    """Construct a valid EpisodeScriptResponse with minimal required fields."""
    from app.api.routes.agent import (
        ArtStyle,
        Character,
        EpisodeScriptResponse,
        Highlight,
        Scene,
        StoryboardPanel,
    )

    return EpisodeScriptResponse(
        episode_number=1,
        episode_title="Pilot",
        story_summary="Alice meets Bob.",
        highlights=[Highlight(title="Meeting", description="first encounter")],
        art_style=ArtStyle(
            base_style="Korean webtoon", color_tone="warm", atmosphere="dramatic"
        ),
        characters=[Character(name="Alice", description="heroine", visual_prompt="")],
        scenes=[Scene(name="Rooftop", description="city rooftop", visual_prompt="")],
        panels=[
            StoryboardPanel(
                id="01-1",
                scene_name="Rooftop",
                scene_description="Alice looks at Bob",
                composition="medium shot, eye level",
                camera_movement="fixed",
                characters=["Alice"],
                voice_character="Alice",
                dialogue="Hello.",
            )
        ],
    )


def _parse_sse_events(raw: str) -> list[tuple[str, str]]:
    """Parse an SSE bytestream into (event, data) pairs.

    Frames are separated by blank lines; each frame carries one ``event:`` and
    one ``data:`` line in our endpoint.
    """
    events: list[tuple[str, str]] = []
    for chunk in raw.split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        evt = None
        data = None
        for line in chunk.splitlines():
            if line.startswith("event:"):
                evt = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data = line[len("data:") :].strip()
        if evt is not None and data is not None:
            events.append((evt, data))
    return events


def test_sse_endpoint_yields_done_event(test_client: TestClient):
    """Successful core run -> progress frame(s) + done frame with response payload."""
    import json as _json

    fake = _fake_response()

    with patch(
        "app.api.routes.agent._generate_episode_script_core",
        new=AsyncMock(return_value=fake),
    ):
        with test_client.stream(
            "POST",
            "/api/v1/agent/episode/1/script/stream",
            json=_make_request_body(),
        ) as resp:
            assert resp.status_code == 200, resp.read()
            assert resp.headers["content-type"].startswith("text/event-stream")
            body = "".join(chunk for chunk in resp.iter_text())

    events = _parse_sse_events(body)
    event_names = [e for e, _ in events]

    assert "progress" in event_names, f"no progress event in {event_names}"
    assert "done" in event_names, f"no done event in {event_names}"
    assert "error" not in event_names, f"unexpected error event: {events}"

    # Last event must be 'done' and carry the serialized response.
    last_evt, last_data = events[-1]
    assert last_evt == "done"
    payload = _json.loads(last_data)
    assert payload["episode_number"] == 1
    assert payload["episode_title"] == "Pilot"
    assert payload["characters"][0]["name"] == "Alice"
    assert payload["panels"][0]["id"] == "01-1"


def test_sse_endpoint_yields_error_on_exception(test_client: TestClient):
    """Core raises -> stream emits an 'error' event and no 'done' event."""
    import json as _json

    with patch(
        "app.api.routes.agent._generate_episode_script_core",
        new=AsyncMock(side_effect=RuntimeError("llm blew up")),
    ):
        with test_client.stream(
            "POST",
            "/api/v1/agent/episode/1/script/stream",
            json=_make_request_body(),
        ) as resp:
            assert resp.status_code == 200, resp.read()
            body = "".join(chunk for chunk in resp.iter_text())

    events = _parse_sse_events(body)
    event_names = [e for e, _ in events]

    assert "error" in event_names, f"no error event in {event_names}"
    assert "done" not in event_names, f"unexpected done event: {events}"

    error_evt = next(e for e in events if e[0] == "error")
    payload = _json.loads(error_evt[1])
    assert "llm blew up" in payload["message"]
