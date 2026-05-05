"""Add performance indexes for foreign key columns used in list queries.

Revision ID: 018
Revises: 017_voice_assets
Create Date: 2026-03-14

Note:
    Earlier migrations already created some of the indexes this migration
    originally tried to (re-)create:

    * ``ix_layer_packs_panel_id`` is created by migration 007.
    * ``ix_clips_timeline_id`` is created by migration 006.

    Re-creating them caused ``index already exists`` errors on a fresh
    SQLite database. They are dropped from this migration entirely so the
    upgrade is a clean no-op for already-indexed columns and so downgrade
    does not race with the earlier migrations' own ``drop_index`` calls.

    The remaining indexes are wrapped in inspector-based guards so the
    migration is idempotent on partially-migrated databases.
"""
from alembic import op
from sqlalchemy import inspect

revision = "018"
down_revision = "017_voice_assets"
branch_labels = None
depends_on = None


# (table, index_name, [columns]) for indexes this migration owns end-to-end.
# Indexes already created by earlier migrations (e.g. ix_layer_packs_panel_id
# from 007, ix_clips_timeline_id from 006) are intentionally excluded.
_INDEXES = [
    ("chapters", "ix_chapters_project_id", ["project_id"]),
    ("panels", "ix_panels_chapter_id", ["chapter_id"]),
    ("render_jobs", "ix_render_jobs_panel_id", ["panel_id"]),
]


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    try:
        return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))
    except Exception:
        return False


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    for table, index_name, columns in _INDEXES:
        if not _index_exists(inspector, table, index_name):
            op.create_index(index_name, table, columns)


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    for table, index_name, _columns in reversed(_INDEXES):
        if _index_exists(inspector, table, index_name):
            op.drop_index(index_name, table)
