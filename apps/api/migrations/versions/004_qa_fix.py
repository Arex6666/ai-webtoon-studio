"""Create QA and fix tables

Revision ID: 004_qa_fix
Revises: 003_render_export
Create Date: 2026-01-15

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '004_qa_fix'
down_revision: Union[str, None] = '003_render_export'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============ RenderAttempts ============
    op.create_table(
        'render_attempts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('render_job_id', sa.String(36), sa.ForeignKey('render_jobs.id'), nullable=False),
        sa.Column('attempt_no', sa.Integer, nullable=False, default=1),
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('ended_at', sa.DateTime, nullable=True),
        sa.Column('error_type', sa.String(50), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('logs_path', sa.String(512), nullable=True),
    )

    # ============ Artifacts ============
    op.create_table(
        'artifacts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('render_job_id', sa.String(36), sa.ForeignKey('render_jobs.id'), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('uri', sa.String(512), nullable=False),
        sa.Column('meta_json', sa.JSON, nullable=False, default={}),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # ============ QAReports ============
    op.create_table(
        'qa_reports',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('render_job_id', sa.String(36), sa.ForeignKey('render_jobs.id'), nullable=False),
        sa.Column('score', sa.Float, nullable=False, default=0.0),
        sa.Column('checks_json', sa.JSON, nullable=False, default={}),
        sa.Column('passed', sa.String(10), default='false'),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # ============ FixPlans ============
    op.create_table(
        'fix_plans',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('render_job_id', sa.String(36), sa.ForeignKey('render_jobs.id'), nullable=False),
        sa.Column('plan_json', sa.JSON, nullable=False, default={}),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table('fix_plans')
    op.drop_table('qa_reports')
    op.drop_table('artifacts')
    op.drop_table('render_attempts')
