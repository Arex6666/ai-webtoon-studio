"""
Database Migration: 添加对话智能体系统模型
添加 conversations, conversation_messages, conversation_actions 表
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON


# revision identifiers
revision = '008_add_conversation_models'
down_revision = '007_layerpack_v1'
branch_labels = None
depends_on = None


def upgrade():
    # 创建 conversations 表
    op.create_table(
        'conversations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('chapter_id', sa.String(36), sa.ForeignKey('chapters.id', ondelete='SET NULL'), nullable=True),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, default='active'),
        sa.Column('current_intent', sa.String(50), nullable=True),
        sa.Column('context_json', JSON, nullable=True),
        sa.Column('message_count', sa.Integer, nullable=False, default=0),
        sa.Column('total_tokens_used', sa.Integer, nullable=False, default=0),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # 创建索引
    op.create_index('ix_conversations_project_id', 'conversations', ['project_id'])
    op.create_index('ix_conversations_chapter_id', 'conversations', ['chapter_id'])
    op.create_index('ix_conversations_status', 'conversations', ['status'])
    op.create_index('ix_conversations_created_at', 'conversations', ['created_at'])

    # 创建 conversation_messages 表
    op.create_table(
        'conversation_messages',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('conversation_id', sa.String(36), sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('intent', sa.String(50), nullable=True),
        sa.Column('entities_json', JSON, nullable=True),
        sa.Column('tool_calls_json', JSON, nullable=True),
        sa.Column('tool_results_json', JSON, nullable=True),
        sa.Column('model_used', sa.String(100), nullable=True),
        sa.Column('tokens_used', sa.Integer, nullable=True),
        sa.Column('latency_ms', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # 创建索引
    op.create_index('ix_conversation_messages_conversation_id', 'conversation_messages', ['conversation_id'])
    op.create_index('ix_conversation_messages_role', 'conversation_messages', ['role'])
    op.create_index('ix_conversation_messages_created_at', 'conversation_messages', ['created_at'])

    # 创建 conversation_actions 表
    op.create_table(
        'conversation_actions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('conversation_id', sa.String(36), sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('message_id', sa.String(36), sa.ForeignKey('conversation_messages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('action_type', sa.String(100), nullable=False),
        sa.Column('action_params_json', JSON, nullable=True),
        sa.Column('status', sa.String(50), nullable=False, default='pending'),
        sa.Column('job_id', sa.String(36), sa.ForeignKey('jobs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('result_json', JSON, nullable=True),
        sa.Column('error_json', JSON, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # 创建索引
    op.create_index('ix_conversation_actions_conversation_id', 'conversation_actions', ['conversation_id'])
    op.create_index('ix_conversation_actions_message_id', 'conversation_actions', ['message_id'])
    op.create_index('ix_conversation_actions_status', 'conversation_actions', ['status'])
    op.create_index('ix_conversation_actions_job_id', 'conversation_actions', ['job_id'])
    op.create_index('ix_conversation_actions_created_at', 'conversation_actions', ['created_at'])


def downgrade():
    # 删除索引
    op.drop_index('ix_conversation_actions_created_at', 'conversation_actions')
    op.drop_index('ix_conversation_actions_job_id', 'conversation_actions')
    op.drop_index('ix_conversation_actions_status', 'conversation_actions')
    op.drop_index('ix_conversation_actions_message_id', 'conversation_actions')
    op.drop_index('ix_conversation_actions_conversation_id', 'conversation_actions')

    op.drop_index('ix_conversation_messages_created_at', 'conversation_messages')
    op.drop_index('ix_conversation_messages_role', 'conversation_messages')
    op.drop_index('ix_conversation_messages_conversation_id', 'conversation_messages')

    op.drop_index('ix_conversations_created_at', 'conversations')
    op.drop_index('ix_conversations_status', 'conversations')
    op.drop_index('ix_conversations_chapter_id', 'conversations')
    op.drop_index('ix_conversations_project_id', 'conversations')

    # 删除表
    op.drop_table('conversation_actions')
    op.drop_table('conversation_messages')
    op.drop_table('conversations')
