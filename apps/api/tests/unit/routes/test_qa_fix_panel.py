"""Bug #18: project_id must be derived from panel.chapter, not panel.project_id.

The Panel model has no ``project_id`` column — it joins to Project
indirectly through Chapter. The original code used
``getattr(panel, 'project_id', None)`` which silently returned ``None``,
causing every fix-job to be created with ``project_id=NULL`` and
breaking project-scoped reporting downstream.
"""
import inspect


def test_qa_fix_does_not_read_panel_project_id():
    from app.api.routes import qa_fix
    src = inspect.getsource(qa_fix)
    assert "panel.project_id" not in src, (
        "qa_fix references panel.project_id, but Panel has no project_id "
        "column. Project must be derived via panel.chapter.project_id."
    )
    assert "getattr(panel, 'project_id'" not in src, (
        "qa_fix uses getattr(panel, 'project_id', ...) which silently "
        "returns None. Use panel.chapter.project_id instead."
    )
    assert 'getattr(panel, "project_id"' not in src, (
        "qa_fix uses getattr(panel, \"project_id\", ...) which silently "
        "returns None. Use panel.chapter.project_id instead."
    )
