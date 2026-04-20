"""Integration tests for POST /api/v1/agent/episode/{n}/generate-panels MinIO persistence.

Task 4 — covers three branches of the Doubao->MinIO sync persistence added in Task 3:

1. Happy path: Doubao returns a temp URL, MinIO upload succeeds -> response carries
   the MinIO key (not the temp URL).
2. MinIO failure: Doubao succeeds, MinIO raises ImageFetchError -> response falls
   back to the temp URL and exposes the error note.
3. Doubao failure: provider returns success=False -> MinIO fetch_and_persist is
   never invoked, response carries the provider error.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _make_body() -> dict:
    """Minimal valid GeneratePanelsRequest body."""
    return {
        "project_id": "proj-minio-test",
        "art_style": {
            "base_style": "Korean webtoon",
            "color_tone": "warm",
            "atmosphere": "dramatic",
        },
        "characters": [
            {"name": "Alice", "description": "heroine", "visual_prompt": "short hair, red coat"},
        ],
        "scenes": [
            {"name": "Rooftop", "description": "city rooftop", "visual_prompt": "city rooftop at sunset"},
        ],
        "panels": [
            {
                "id": "01-1",
                "scene_name": "Rooftop",
                "scene_description": "Alice looks over the city",
                "composition": "medium shot, eye level",
                "camera_movement": "fixed",
                "characters": ["Alice"],
            },
        ],
    }


def _mock_provider(success: bool, image_url: str | None = None, error: str | None = None):
    """Build an object whose .generate() returns a DoubaoImageResult-shaped value."""
    from app.services.layer_factory.doubao_image_provider import DoubaoImageResult

    provider = MagicMock()
    provider.generate = AsyncMock(
        return_value=DoubaoImageResult(
            success=success,
            image_url=image_url,
            error=error,
        )
    )
    return provider


def test_generate_panels_persists_to_minio(test_client: TestClient):
    """Doubao returns a temp URL -> fetch_and_persist returns a MinIO key -> response carries the key."""
    provider = _mock_provider(success=True, image_url="https://doubao.temp/a.png")
    minio_key = "agent-commit/proj-minio-test/panel/ep1-p01_1-abcdef12.png"

    with patch(
        "app.api.routes.agent.get_doubao_image_provider",
        return_value=provider,
    ), patch(
        "app.services.agent_commit.image_fetcher.fetch_and_persist",
        new=AsyncMock(return_value=minio_key),
    ) as mock_persist:
        resp = test_client.post(
            "/api/v1/agent/episode/1/generate-panels",
            json=_make_body(),
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["panels"]) == 1
    panel = body["panels"][0]
    assert panel["status"] == "success"
    assert panel["image_url"] == minio_key
    assert panel.get("error") in (None, "")
    mock_persist.assert_awaited_once()
    # Sanity-check kwargs — route passes project_id, asset_type, name_hint.
    kwargs = mock_persist.await_args.kwargs
    assert kwargs["project_id"] == "proj-minio-test"
    assert kwargs["asset_type"] == "panel"
    assert "01-1" in kwargs["name_hint"]


def test_generate_panels_minio_failure_falls_back_to_temp_url(test_client: TestClient):
    """MinIO upload fails -> response keeps Doubao temp URL and surfaces error note."""
    from app.services.agent_commit.image_fetcher import ImageFetchError

    temp_url = "https://doubao.temp/b.png"
    provider = _mock_provider(success=True, image_url=temp_url)

    with patch(
        "app.api.routes.agent.get_doubao_image_provider",
        return_value=provider,
    ), patch(
        "app.services.agent_commit.image_fetcher.fetch_and_persist",
        new=AsyncMock(side_effect=ImageFetchError("minio upload failed: boom")),
    ) as mock_persist:
        resp = test_client.post(
            "/api/v1/agent/episode/1/generate-panels",
            json=_make_body(),
        )

    assert resp.status_code == 200, resp.text
    panel = resp.json()["panels"][0]
    assert panel["status"] == "success"
    assert panel["image_url"] == temp_url
    assert panel["error"] and "minio persist failed" in panel["error"]
    mock_persist.assert_awaited_once()


def test_generate_panels_doubao_failure_no_minio_attempted(test_client: TestClient):
    """Doubao returns success=False -> fetch_and_persist must not be called."""
    provider = _mock_provider(success=False, image_url=None, error="rate limited")

    with patch(
        "app.api.routes.agent.get_doubao_image_provider",
        return_value=provider,
    ), patch(
        "app.services.agent_commit.image_fetcher.fetch_and_persist",
        new=AsyncMock(),
    ) as mock_persist:
        resp = test_client.post(
            "/api/v1/agent/episode/1/generate-panels",
            json=_make_body(),
        )

    assert resp.status_code == 200, resp.text
    panel = resp.json()["panels"][0]
    assert panel["status"] == "failed"
    assert panel["image_url"] is None
    assert panel["error"] == "rate limited"
    mock_persist.assert_not_awaited()
