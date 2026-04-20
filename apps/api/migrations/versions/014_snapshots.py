"""E3: Create snapshots and patch_records tables

Revision ID: 014_snapshots
Revises: 013_action_approval
Create Date: 2026-02-13

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "014_snapshots"
down_revision: Union[str, None] = "013_action_approval"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=True),
        sa.Column("chapter_id", sa.String(36), nullable=True),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("snapshots.id"), nullable=True),
        sa.Column("snapshot_type", sa.String(30), nullable=False, server_default="auto"),
        sa.Column("data_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_snapshots_entity_lookup", "snapshots", ["entity_type", "entity_id", "created_at"])

    op.create_table(
        "patch_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("patches_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("before_snapshot_id", sa.String(36), sa.ForeignKey("snapshots.id"), nullable=True),
        sa.Column("after_snapshot_id", sa.String(36), sa.ForeignKey("snapshots.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("patch_records")
    op.drop_index("ix_snapshots_entity_lookup", table_name="snapshots")
    op.drop_table("snapshots")
