"""add preview_key to panels

Revision ID: 021_panel_preview_key
Revises: 020_job_celery_task_id
Create Date: 2026-05-05

Architectural follow-up to Bug #18 (the 7-day TTL widening): Panel.preview_url
stores a presigned URL with finite TTL, so links break when the TTL expires.
Add a separate preview_key column that holds the raw storage key, and have
readers re-sign on demand. Existing rows pre-migration won't have a key; the
re-sign helper falls back to the legacy preview_url field for back-compat.
"""
from alembic import op
import sqlalchemy as sa


revision = "021_panel_preview_key"
down_revision = "020_job_celery_task_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "panels",
        sa.Column("preview_key", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("panels", "preview_key")
