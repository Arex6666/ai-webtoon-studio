"""Integration tests for real tool handlers.

Covers the 3 recently-implemented handlers on
``app.services.conversation.tool_handlers.ToolHandlers``:

- ``render_panels``: happy path (queues a Celery image job per panel) and
  error path (unknown chapter_id).
- ``analyze_quality``: uses ``ImageQAService`` via a patched mock.
- ``suggest_fixes``: delegates to ``FixPlanGenerator``'s module-level
  ``generate_fix_options`` / ``get_best_fix`` for real strategies.
"""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(autouse=True)
def _auth_off(monkeypatch):
    monkeypatch.setenv("ENABLE_AUTH", "false")


@pytest.fixture
def panel_in_db(test_client):
    """Seed a minimal Project/Chapter/Panel tree and return their IDs."""
    from app.core.database import SessionLocal
    from app.models.project import Project
    from app.models.chapter import Chapter
    from app.models.panel import Panel

    db = SessionLocal()
    try:
        proj = Project(id=str(uuid.uuid4()), name="TH", description="")
        ch = Chapter(
            id=str(uuid.uuid4()),
            project_id=proj.id,
            title="ep1",
            script_raw="",
        )
        panel = Panel(
            id=str(uuid.uuid4()),
            chapter_id=ch.id,
            order_index=0,
            spec_json={},
            preview_url="http://minio/test/preview.png",
        )
        db.add_all([proj, ch, panel])
        db.commit()
        return {
            "project_id": proj.id,
            "chapter_id": ch.id,
            "panel_id": panel.id,
        }
    finally:
        db.close()


class TestRenderPanelsHandler:
    """Happy + error paths for render_panels."""

    @pytest.mark.asyncio
    async def test_queues_celery_job_per_panel(self, panel_in_db):
        from app.core.database import SessionLocal
        from app.services.conversation.tool_handlers import ToolHandlers

        # Patch the Celery task at its source module so the handler's
        # late-bound import picks up the mock.
        fake_delay = MagicMock(return_value=MagicMock(id="celery-task-1"))
        with patch(
            "app.workers.image_worker.execute_image_job.delay",
            fake_delay,
        ):
            db = SessionLocal()
            try:
                handlers = ToolHandlers(db=db)
                result = await handlers.render_panels(
                    chapter_id=panel_in_db["chapter_id"],
                    panel_ids=None,
                    quality="draft",
                )
            finally:
                db.close()

        assert result["success"] is True
        assert result["chapter_id"] == panel_in_db["chapter_id"]
        assert result["queued_count"] == 1
        assert len(result["jobs"]) == 1
        job_entry = result["jobs"][0]
        assert job_entry["panel_id"] == panel_in_db["panel_id"]
        assert job_entry["task_id"] == "celery-task-1"
        assert job_entry["job_id"]
        # Celery task was dispatched exactly once.
        fake_delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_chapter_not_found_returns_error(self, panel_in_db):
        from app.core.database import SessionLocal
        from app.services.conversation.tool_handlers import ToolHandlers

        db = SessionLocal()
        try:
            handlers = ToolHandlers(db=db)
            result = await handlers.render_panels(
                chapter_id="nonexistent-chapter-id",
            )
        finally:
            db.close()

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_requires_chapter_or_panel_ids(self, panel_in_db):
        from app.core.database import SessionLocal
        from app.services.conversation.tool_handlers import ToolHandlers

        db = SessionLocal()
        try:
            handlers = ToolHandlers(db=db)
            result = await handlers.render_panels()
        finally:
            db.close()

        assert result["success"] is False
        assert "chapter_id or panel_ids required" in result["error"]


class TestAnalyzeQualityHandler:
    """Happy path for analyze_quality using a mocked ImageQAService."""

    @pytest.mark.asyncio
    async def test_runs_qa_on_panel_preview(self, panel_in_db):
        from app.core.database import SessionLocal
        from app.services.conversation.tool_handlers import ToolHandlers

        fake_report = MagicMock()
        fake_report.to_dict = MagicMock(
            return_value={
                "passed": True,
                "score": 0.85,
                "issues": [],
                "checks_performed": ["black_image", "blurry"],
            }
        )
        fake_service = MagicMock()
        fake_service.analyze = AsyncMock(return_value=fake_report)

        with patch(
            "app.services.qa.image_qa.ImageQAService",
            return_value=fake_service,
        ):
            db = SessionLocal()
            try:
                handlers = ToolHandlers(db=db)
                result = await handlers.analyze_quality(
                    panel_id=panel_in_db["panel_id"],
                )
            finally:
                db.close()

        assert result["success"] is True
        analysis = result["analysis"]
        assert analysis["panel_id"] == panel_in_db["panel_id"]
        assert analysis["overall_score"] == 0.85
        assert analysis["passed"] is True
        assert analysis["issues"] == []
        assert "black_image" in analysis["checks_performed"]
        # ImageQAService.analyze called once with the panel's preview_url.
        fake_service.analyze.assert_awaited_once_with(
            "http://minio/test/preview.png"
        )

    @pytest.mark.asyncio
    async def test_panel_not_found(self, panel_in_db):
        from app.core.database import SessionLocal
        from app.services.conversation.tool_handlers import ToolHandlers

        db = SessionLocal()
        try:
            handlers = ToolHandlers(db=db)
            result = await handlers.analyze_quality(panel_id="nonexistent")
        finally:
            db.close()

        assert result["success"] is False


class TestSuggestFixesHandler:
    """Happy path for suggest_fixes using real FixPlanGenerator strategies."""

    @pytest.mark.asyncio
    async def test_generates_fix_options_for_known_issue_codes(
        self, panel_in_db
    ):
        from app.core.database import SessionLocal
        from app.services.conversation.tool_handlers import ToolHandlers

        db = SessionLocal()
        try:
            handlers = ToolHandlers(db=db)
            result = await handlers.suggest_fixes(
                panel_id=panel_in_db["panel_id"],
                issues=["BLACK_IMAGE", "BLURRY"],
            )
        finally:
            db.close()

        assert result["success"] is True
        assert result["panel_id"] == panel_in_db["panel_id"]
        fix_plan = result["fix_plan"]
        # FixPlanGenerator returns at least one option for BLACK_IMAGE/BLURRY.
        assert len(fix_plan["options"]) > 0
        assert fix_plan["best_option"] is not None
        # Each option must carry a description + fix_type.
        for opt in fix_plan["options"]:
            assert opt["description"]
            assert opt["fix_type"]
        # Back-compat suggestions list emits one entry per input issue.
        assert len(result["suggestions"]) == 2
        assert {s["issue"] for s in result["suggestions"]} == {
            "BLACK_IMAGE",
            "BLURRY",
        }

    @pytest.mark.asyncio
    async def test_accepts_qa_report_dict(self, panel_in_db):
        from app.core.database import SessionLocal
        from app.services.conversation.tool_handlers import ToolHandlers

        db = SessionLocal()
        try:
            handlers = ToolHandlers(db=db)
            result = await handlers.suggest_fixes(
                panel_id=panel_in_db["panel_id"],
                qa_report={
                    "issues": [
                        {
                            "code": "BLACK_IMAGE",
                            "level": "error",
                            "message": "solid black",
                        }
                    ]
                },
            )
        finally:
            db.close()

        assert result["success"] is True
        assert len(result["fix_plan"]["options"]) > 0

    @pytest.mark.asyncio
    async def test_empty_issues_returns_empty_plan(self, panel_in_db):
        from app.core.database import SessionLocal
        from app.services.conversation.tool_handlers import ToolHandlers

        db = SessionLocal()
        try:
            handlers = ToolHandlers(db=db)
            result = await handlers.suggest_fixes(
                panel_id=panel_in_db["panel_id"],
                issues=[],
            )
        finally:
            db.close()

        assert result["success"] is True
        assert result["suggestions"] == []
        assert result["fix_plan"]["options"] == []
        assert result["fix_plan"]["best_option"] is None
