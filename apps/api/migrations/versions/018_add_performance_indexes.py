"""Add performance indexes for foreign key columns used in list queries.

Revision ID: 018
Revises: 017
Create Date: 2026-03-14
"""
from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_chapters_project_id", "chapters", ["project_id"])
    op.create_index("ix_panels_chapter_id", "panels", ["chapter_id"])
    op.create_index("ix_render_jobs_panel_id", "render_jobs", ["panel_id"])
    op.create_index("ix_layer_packs_panel_id", "layer_packs", ["panel_id"])
    op.create_index("ix_clips_timeline_id", "clips", ["timeline_id"])


def downgrade():
    op.drop_index("ix_clips_timeline_id", "clips")
    op.drop_index("ix_layer_packs_panel_id", "layer_packs")
    op.drop_index("ix_render_jobs_panel_id", "render_jobs")
    op.drop_index("ix_panels_chapter_id", "panels")
    op.drop_index("ix_chapters_project_id", "chapters")
