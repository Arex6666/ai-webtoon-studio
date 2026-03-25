"""Tests for the unified POST /api/v1/jobs endpoint."""
import pytest
from app.schemas.job_schemas import JobCreateRequest, JobStatusResponse


class TestJobCreateRequest:
    def test_image_job_schema(self):
        req = JobCreateRequest(type="image", target_id="panel-001", provider="doubao", params={"force_regenerate": True})
        assert req.type == "image"
        assert req.target_id == "panel-001"

    def test_video_job_schema(self):
        req = JobCreateRequest(type="video", target_id="clip-001", provider="doubao",
            params={"start_frame_url": "https://storage/frame.png", "motion_prompt": "camera zoom in", "duration_sec": 3.0, "fps": 24})
        assert req.type == "video"
        assert req.params["duration_sec"] == 3.0

    def test_default_provider(self):
        req = JobCreateRequest(type="storyboard", target_id="chapter-001")
        assert req.provider == "mock"
        assert req.params == {}

    def test_canceled_spelling(self):
        resp = JobStatusResponse(job_id="job-001", type="image", status="canceled")
        assert resp.status == "canceled"


class TestJobStatusResponse:
    def test_minimal_response(self):
        resp = JobStatusResponse(job_id="job-001", type="image", status="queued")
        assert resp.progress == 0.0
        assert resp.result is None

    def test_completed_response(self):
        resp = JobStatusResponse(job_id="job-001", type="image", status="succeeded", progress=1.0, result={"preview_url": "https://storage/preview.png"})
        assert resp.progress == 1.0
