"""add celery_task_id to jobs

Revision ID: 020_job_celery_task_id
Revises: 019_add_clip_columns
Create Date: 2026-05-04

Bug #4 follow-up: cancel_job needs the Celery AsyncResult.id (not our DB pk)
in order to actually revoke a running task. Existing rows pre-migration won't
have a value; cancel_job will return 409 in that case.
"""
from alembic import op
import sqlalchemy as sa


revision = "020_job_celery_task_id"
down_revision = "019_add_clip_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_jobs_celery_task_id", "jobs", ["celery_task_id"])


def downgrade() -> None:
    op.drop_index("ix_jobs_celery_task_id", table_name="jobs")
    op.drop_column("jobs", "celery_task_id")
