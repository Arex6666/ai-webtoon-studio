"""
Database Migration: Task A05 - LayerPack 扩展
添加 attempt, manifest_url, full_url, generation_params 字段
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '007_layerpack_v1'
down_revision = '006_timeline_bindings_job'
branch_labels = None
depends_on = None


def upgrade():
    # 添加新字段到 layer_packs 表
    op.add_column('layer_packs', sa.Column('attempt', sa.Integer, default=1))
    op.add_column('layer_packs', sa.Column('manifest_url', sa.String(512), nullable=True))
    op.add_column('layer_packs', sa.Column('full_url', sa.String(512), nullable=True))
    op.add_column('layer_packs', sa.Column('generation_params', sa.JSON, nullable=True))
    
    # 创建索引
    op.create_index('ix_layer_packs_panel_id', 'layer_packs', ['panel_id'])
    op.create_index('ix_layer_packs_attempt', 'layer_packs', ['attempt'])


def downgrade():
    op.drop_index('ix_layer_packs_attempt', 'layer_packs')
    op.drop_index('ix_layer_packs_panel_id', 'layer_packs')
    op.drop_column('layer_packs', 'generation_params')
    op.drop_column('layer_packs', 'full_url')
    op.drop_column('layer_packs', 'manifest_url')
    op.drop_column('layer_packs', 'attempt')
