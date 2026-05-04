"""Add reference image fields to assets table.

Revision ID: 003_add_asset_reference_fields
Revises: 002_tables_part2
Create Date: 2026-01-20
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "003_add_asset_reference_fields"
down_revision: Union[str, None] = "002_tables_part2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # S5-01: columns required by Asset.reference_image_* fields
    # Use batch_alter_table for SQLite compatibility (SQLite doesn't support
    # ALTER COLUMN DROP DEFAULT directly; batch mode recreates the table).
    with op.batch_alter_table("assets") as batch_op:
        batch_op.add_column(
            sa.Column("reference_image_path", sa.String(512), nullable=True),
        )
        batch_op.add_column(
            sa.Column(
                "reference_image_status",
                sa.String(50),
                nullable=False,
                server_default="none",
            ),
        )
        batch_op.add_column(
            sa.Column("reference_image_meta", sa.JSON, nullable=True),
        )

    # set default value on existing rows then drop the temporary server_default
    op.execute(
        "UPDATE assets SET reference_image_status = 'none' "
        "WHERE reference_image_status IS NULL"
    )
    with op.batch_alter_table("assets") as batch_op:
        batch_op.alter_column("reference_image_status", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("assets") as batch_op:
        batch_op.drop_column("reference_image_meta")
        batch_op.drop_column("reference_image_status")
        batch_op.drop_column("reference_image_path")
