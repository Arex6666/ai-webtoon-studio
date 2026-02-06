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
    op.add_column(
        "assets",
        sa.Column("reference_image_path", sa.String(512), nullable=True),
    )
    op.add_column(
        "assets",
        sa.Column(
            "reference_image_status",
            sa.String(50),
            nullable=False,
            server_default="none",
        ),
    )
    op.add_column(
        "assets",
        sa.Column("reference_image_meta", sa.JSON, nullable=True),
    )

    # set default value on existing rows then drop the temporary server_default
    op.execute(
        "UPDATE assets SET reference_image_status = 'none' "
        "WHERE reference_image_status IS NULL"
    )
    op.alter_column("assets", "reference_image_status", server_default=None)


def downgrade() -> None:
    op.drop_column("assets", "reference_image_meta")
    op.drop_column("assets", "reference_image_status")
    op.drop_column("assets", "reference_image_path")
