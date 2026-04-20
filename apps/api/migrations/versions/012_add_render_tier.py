"""E1: Add render tier column to jobs table

Revision ID: 012_render_tier
Revises: 011_conv_episode
Create Date: 2026-02-13

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "012_render_tier"
down_revision: Union[str, None] = "011_conv_episode"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("tier", sa.String(20), nullable=True, server_default="normal"))


def downgrade() -> None:
    op.drop_column("jobs", "tier")
