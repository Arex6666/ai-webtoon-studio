"""Add episode_number to conversations table

Revision ID: 011_conv_episode
Revises: b9a98c1685f5
Create Date: 2026-02-03

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "011_conv_episode"
down_revision: Union[str, None] = "b9a98c1685f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 添加 episode_number 列到 conversations 表
    op.add_column(
        "conversations",
        sa.Column("episode_number", sa.Integer(), nullable=True)
    )
    
    # 创建索引以加速按项目+分集查询
    op.create_index(
        "ix_conversations_project_episode",
        "conversations",
        ["project_id", "episode_number"]
    )


def downgrade() -> None:
    op.drop_index("ix_conversations_project_episode", table_name="conversations")
    op.drop_column("conversations", "episode_number")
