"""E2: Add approval columns to conversation_actions

Revision ID: 013_action_approval
Revises: 012_render_tier
Create Date: 2026-02-13

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "013_action_approval"
down_revision: Union[str, None] = "012_render_tier"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("conversation_actions", sa.Column("requires_approval", sa.Boolean(), nullable=True, server_default="false"))
    op.add_column("conversation_actions", sa.Column("approval_status", sa.String(30), nullable=True, server_default="auto"))
    op.add_column("conversation_actions", sa.Column("approved_by", sa.String(100), nullable=True))
    op.add_column("conversation_actions", sa.Column("approved_at", sa.DateTime(), nullable=True))
    op.add_column("conversation_actions", sa.Column("rejected_reason", sa.Text(), nullable=True))
    op.add_column("conversation_actions", sa.Column("cost_estimate", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("conversation_actions", "cost_estimate")
    op.drop_column("conversation_actions", "rejected_reason")
    op.drop_column("conversation_actions", "approved_at")
    op.drop_column("conversation_actions", "approved_by")
    op.drop_column("conversation_actions", "approval_status")
    op.drop_column("conversation_actions", "requires_approval")
