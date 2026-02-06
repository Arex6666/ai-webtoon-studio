"""Create export and revision tables

Revision ID: 005_export_revision
Revises: 004_qa_fix
Create Date: 2026-01-15

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '005_export_revision'
down_revision: Union[str, None] = '004_qa_fix'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============ Exports ============
    op.create_table(
        'exports',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('chapter_id', sa.String(36), sa.ForeignKey('chapters.id'), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('state', sa.String(50), default='queued'),
        sa.Column('settings_json', sa.JSON, nullable=False, default={}),
        sa.Column('output_uri', sa.String(512), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # ============ ExportJobs ============
    op.create_table(
        'export_jobs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('export_id', sa.String(36), sa.ForeignKey('exports.id'), nullable=False),
        sa.Column('attempt_count', sa.Integer, default=0),
        sa.Column('logs_path', sa.String(512), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # ============ Revisions ============
    op.create_table(
        'revisions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('chapter_id', sa.String(36), sa.ForeignKey('chapters.id'), nullable=False),
        sa.Column('revision_number', sa.Integer, nullable=False),
        sa.Column('change_type', sa.String(50), nullable=False),
        sa.Column('target_id', sa.String(36), nullable=True),
        sa.Column('snapshot_json', sa.JSON, nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('created_by', sa.String(36), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('revisions')
    op.drop_table('export_jobs')
    op.drop_table('exports')
