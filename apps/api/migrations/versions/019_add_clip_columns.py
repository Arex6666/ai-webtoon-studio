"""Add negative and seed columns to clips table.

Revision ID: 019_add_clip_columns
Revises: 018
"""
from alembic import op
import sqlalchemy as sa

revision = "019_add_clip_columns"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("clips", sa.Column("negative", sa.Text(), nullable=True))
    op.add_column("clips", sa.Column("seed", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("clips", "seed")
    op.drop_column("clips", "negative")
