"""Initial migration - create all tables

Revision ID: 001_initial
Revises:
Create Date: 2026-01-15

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============ Studios ============
    op.create_table(
        'studios',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('quota_json', sa.JSON, nullable=False, default={}),
        sa.Column('default_style_profile_id', sa.String(36), nullable=True),
        sa.Column('member_count', sa.Integer, default=1),
        sa.Column('status', sa.String(50), default='active'),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # ============ Projects ============
    op.create_table(
        'projects',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('studio_id', sa.String(36), sa.ForeignKey('studios.id'), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('cover_image', sa.String(512), nullable=True),
        sa.Column('is_archived', sa.Boolean, default=False),
        sa.Column('default_style_profile_id', sa.String(36), nullable=True),
        sa.Column('target_platform', sa.String(50), default='webtoon'),
        sa.Column('default_resolution', sa.String(50), default='1080x1920'),
        sa.Column('default_render_tier', sa.String(50), default='normal'),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # ============ Chapters ============
    op.create_table(
        'chapters',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('order_index', sa.Integer, default=0),
        sa.Column('script_raw', sa.Text, nullable=True),
        sa.Column('layout_json', sa.JSON, nullable=False, default={}),
        sa.Column('status', sa.String(50), default='draft'),
        sa.Column('export_status', sa.String(50), default='draft'),
        sa.Column('exported_url', sa.String(512), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # ============ Assets ============
    op.create_table(
        'assets',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('tags', sa.JSON, nullable=False, default=[]),
        sa.Column('thumbnail_url', sa.String(512), nullable=True),
        sa.Column('current_version_id', sa.String(36), nullable=True),
        sa.Column('data_json', sa.JSON, nullable=False, default={}),
        sa.Column('status', sa.String(50), default='active'),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # ============ Panels ============
    op.create_table(
        'panels',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('chapter_id', sa.String(36), sa.ForeignKey('chapters.id'), nullable=False),
        sa.Column('order_index', sa.Integer, default=0),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('summary', sa.Text, nullable=True),
        sa.Column('duration_s', sa.Float, default=3.0),
        sa.Column('aspect_ratio', sa.String(20), default='9:16'),
        sa.Column('spec_json', sa.JSON, nullable=False, default={}),
        sa.Column('current_version_id', sa.String(36), nullable=True),
        sa.Column('render_status', sa.String(50), default='draft'),
        sa.Column('active_layer_pack_id', sa.String(36), nullable=True),
        sa.Column('preview_url', sa.String(512), nullable=True),
        sa.Column('typeset_status', sa.String(50), default='pending'),
        sa.Column('typeset_image_url', sa.String(512), nullable=True),
        sa.Column('qa_score', sa.Float, default=0.0),
        sa.Column('needs_manual_fix', sa.String(50), default='false'),
        sa.Column('warning_count', sa.Integer, default=0),
        sa.Column('error_count', sa.Integer, default=0),
        sa.Column('render_tier', sa.String(50), default='normal'),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # 继续在 002_tables_part2 中创建其他表


def downgrade() -> None:
    op.drop_table('panels')
    op.drop_table('assets')
    op.drop_table('chapters')
    op.drop_table('projects')
    op.drop_table('studios')
