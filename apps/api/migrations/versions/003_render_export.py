"""Create render and export tables

Revision ID: 003_render_export
Revises: 002_tables_part2
Create Date: 2026-01-15

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '003_render_export'
down_revision: Union[str, None] = '002_tables_part2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============ RenderJobs ============
    op.create_table(
        'render_jobs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('shot_version_id', sa.String(36), nullable=True),
        sa.Column('panel_id', sa.String(36), sa.ForeignKey('panels.id'), nullable=True),
        sa.Column('chapter_id', sa.String(36), nullable=True),
        sa.Column('engine', sa.String(50), default='comfyui'),
        sa.Column('tier', sa.String(50), default='normal'),
        sa.Column('job_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('priority', sa.Integer, default=0),
        sa.Column('idempotency_key', sa.String(255), nullable=True),
        sa.Column('progress', sa.Float, default=0),
        sa.Column('current_step', sa.String(255), nullable=True),
        sa.Column('payload_json', sa.JSON, nullable=True),
        sa.Column('input_params', sa.JSON, nullable=False, default={}),
        sa.Column('output_data', sa.JSON, nullable=True),
        sa.Column('result_url', sa.String(512), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('retry_count', sa.Integer, default=0),
        sa.Column('max_retries', sa.Integer, default=3),
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # ============ LayerPacks ============
    op.create_table(
        'layer_packs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('panel_id', sa.String(36), sa.ForeignKey('panels.id'), nullable=False),
        sa.Column('version', sa.Integer, default=1),
        sa.Column('parent_id', sa.String(36), sa.ForeignKey('layer_packs.id'), nullable=True),
        sa.Column('is_active', sa.String(10), default='true'),
        sa.Column('file_full', sa.String(512), nullable=True),
        sa.Column('file_char', sa.String(512), nullable=True),
        sa.Column('file_bg', sa.String(512), nullable=True),
        sa.Column('file_fg', sa.String(512), nullable=True),
        sa.Column('file_mask', sa.String(512), nullable=True),
        sa.Column('file_depth', sa.String(512), nullable=True),
        sa.Column('file_lineart', sa.String(512), nullable=True),
        sa.Column('extra_files', sa.JSON, nullable=False, default={}),
        sa.Column('width', sa.Integer, nullable=True),
        sa.Column('height', sa.Integer, nullable=True),
        sa.Column('bbox_json', sa.JSON, nullable=False, default={}),
        sa.Column('params_json', sa.JSON, nullable=False, default={}),
        sa.Column('qa_score', sa.Float, default=0.0),
        sa.Column('qa_passed', sa.String(10), default='false'),
        sa.Column('qa_json', sa.JSON, nullable=False, default={}),
        sa.Column('status', sa.String(50), default='completed'),
        sa.Column('metadata_json', sa.JSON, nullable=False, default={}),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table('layer_packs')
    op.drop_table('render_jobs')
