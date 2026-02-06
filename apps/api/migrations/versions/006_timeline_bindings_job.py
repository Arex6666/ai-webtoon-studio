"""
Database Migration: Task A02 - Timeline, Bindings, Job tables
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '006_timeline_bindings_job'
down_revision = '005_export_revision'
branch_labels = None
depends_on = None


def upgrade():
    # Timeline 表
    op.create_table(
        'timelines',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('chapter_id', sa.String(36), sa.ForeignKey('chapters.id'), nullable=False, unique=True),
        sa.Column('settings_json', sa.JSON, nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Clip 表
    op.create_table(
        'clips',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('timeline_id', sa.String(36), sa.ForeignKey('timelines.id'), nullable=False),
        sa.Column('panel_id', sa.String(36), sa.ForeignKey('panels.id'), nullable=False),
        sa.Column('order_index', sa.Integer, default=0),
        sa.Column('duration_sec', sa.Float, default=3.0),
        sa.Column('fps', sa.Integer, default=8),
        sa.Column('provider', sa.String(50), default='mock'),
        sa.Column('motion_prompt', sa.Text, nullable=True),
        sa.Column('motion_mode', sa.String(50), default='single_keyframe'),
        sa.Column('start_frame_layerpack_id', sa.String(36), nullable=True),
        sa.Column('end_frame_layerpack_id', sa.String(36), nullable=True),
        sa.Column('status', sa.String(50), default='Draft'),
        sa.Column('progress', sa.Float, default=0.0),
        sa.Column('output_json', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ChapterBindings 表
    op.create_table(
        'chapter_bindings',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('chapter_id', sa.String(36), sa.ForeignKey('chapters.id'), nullable=False, unique=True),
        sa.Column('identity_asset_ids', sa.JSON, nullable=False, server_default='[]'),
        sa.Column('scene_asset_ids', sa.JSON, nullable=False, server_default='[]'),
        sa.Column('anchor_ids', sa.JSON, nullable=False, server_default='[]'),
        sa.Column('style_profile_id', sa.String(36), nullable=True),
        sa.Column('qa_config_json', sa.JSON, nullable=True),
        sa.Column('retry_policy_json', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Job 表
    op.create_table(
        'jobs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id'), nullable=True),
        sa.Column('chapter_id', sa.String(36), sa.ForeignKey('chapters.id'), nullable=True),
        sa.Column('panel_id', sa.String(36), sa.ForeignKey('panels.id'), nullable=True),
        sa.Column('clip_id', sa.String(36), nullable=True),
        sa.Column('provider', sa.String(50), default='mock'),
        sa.Column('attempt', sa.Integer, default=1),
        sa.Column('max_attempts', sa.Integer, default=3),
        sa.Column('status', sa.String(50), default='queued'),
        sa.Column('progress', sa.Float, default=0.0),
        sa.Column('eta_seconds', sa.Integer, nullable=True),
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('finished_at', sa.DateTime, nullable=True),
        sa.Column('cost_estimated', sa.Float, default=0.0),
        sa.Column('cost_used', sa.Float, default=0.0),
        sa.Column('inputs_json', sa.JSON, nullable=False, server_default='{}'),
        sa.Column('outputs_json', sa.JSON, nullable=True),
        sa.Column('qa_json', sa.JSON, nullable=True),
        sa.Column('error_json', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # 创建索引
    op.create_index('ix_clips_timeline_id', 'clips', ['timeline_id'])
    op.create_index('ix_clips_panel_id', 'clips', ['panel_id'])
    op.create_index('ix_jobs_chapter_id', 'jobs', ['chapter_id'])
    op.create_index('ix_jobs_panel_id', 'jobs', ['panel_id'])
    op.create_index('ix_jobs_status', 'jobs', ['status'])
    op.create_index('ix_jobs_type', 'jobs', ['type'])


def downgrade():
    op.drop_index('ix_jobs_type', 'jobs')
    op.drop_index('ix_jobs_status', 'jobs')
    op.drop_index('ix_jobs_panel_id', 'jobs')
    op.drop_index('ix_jobs_chapter_id', 'jobs')
    op.drop_index('ix_clips_panel_id', 'clips')
    op.drop_index('ix_clips_timeline_id', 'clips')
    op.drop_table('jobs')
    op.drop_table('chapter_bindings')
    op.drop_table('clips')
    op.drop_table('timelines')
