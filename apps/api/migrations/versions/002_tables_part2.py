"""Create remaining tables part 2

Revision ID: 002_tables_part2
Revises: 001_initial
Create Date: 2026-01-15

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002_tables_part2'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============ ShotVersions ============
    op.create_table(
        'shot_versions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('panel_id', sa.String(36), sa.ForeignKey('panels.id'), nullable=False),
        sa.Column('version_no', sa.Integer, nullable=False, default=1),
        sa.Column('shot_spec_json', sa.JSON, nullable=False, default={}),
        sa.Column('style_profile_id', sa.String(36), nullable=True),
        sa.Column('commit_message', sa.Text, nullable=True),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # ============ AssetVersions ============
    op.create_table(
        'asset_versions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('asset_id', sa.String(36), sa.ForeignKey('assets.id'), nullable=False),
        sa.Column('version_no', sa.Integer, nullable=False, default=1),
        sa.Column('manifest_json', sa.JSON, nullable=False, default={}),
        sa.Column('vector_id', sa.String(36), nullable=True),
        sa.Column('commit_message', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # ============ FaceEmbeddings ============
    op.create_table(
        'face_embeddings',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('character_asset_id', sa.String(36), sa.ForeignKey('assets.id'), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False, default='insightface'),
        sa.Column('embedding_path', sa.String(512), nullable=False),
        sa.Column('reference_image_path', sa.String(512), nullable=True),
        sa.Column('quality_score', sa.Float, default=0.0),
        sa.Column('status', sa.String(50), default='active'),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # ============ SceneAnchors ============
    op.create_table(
        'scene_anchors',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('scene_asset_id', sa.String(36), sa.ForeignKey('assets.id'), nullable=False),
        sa.Column('bg_anchor_path', sa.String(512), nullable=False),
        sa.Column('control_maps', sa.JSON, nullable=False, default={}),
        sa.Column('perspective_json', sa.JSON, nullable=True),
        sa.Column('status', sa.String(50), default='active'),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table('scene_anchors')
    op.drop_table('face_embeddings')
    op.drop_table('asset_versions')
    op.drop_table('shot_versions')
