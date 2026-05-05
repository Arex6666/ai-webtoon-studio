"""Bug #5: delete_project should rely on ORM cascades, not raw bulk deletes.

The original implementation walked every related model and issued
``db.query(...).delete(synchronize_session=False)`` for each. That:

- bypasses ORM cascade rules (so any cascade-only logic, like
  ``delete-orphan`` on grandchildren, never runs);
- silently misses any new related model added later;
- needs to be edited every time the schema grows.

The Project's ``relationship(...)`` declarations already carry
``cascade="all, delete-orphan"`` for chapters, assets, jobs,
prop_assets, asset_relations, conversations (and voice_agents,
music_assets, snapshots via backref). Replacing the manual chain with
a single ``db.delete(project); db.commit()`` is correct and keeps the
delete logic colocated with the schema.
"""
import inspect


def test_delete_project_relies_on_orm_cascade():
    from app.api.routes import projects as projects_route
    src = inspect.getsource(projects_route.delete_project)
    raw_delete_count = src.count(".delete(synchronize_session=False)")
    assert raw_delete_count <= 1, (
        f"delete_project still has {raw_delete_count} raw bulk-deletes; "
        f"should use db.delete(project) and let ORM cascade handle children."
    )
