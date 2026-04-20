"""E4: Create provider_cost_configs table

Revision ID: 015_cost_config
Revises: 014_snapshots
Create Date: 2026-02-13

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "015_cost_config"
down_revision: Union[str, None] = "014_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provider_cost_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(50), unique=True, nullable=False),
        sa.Column("cost_per_image", sa.Float(), server_default="0.0"),
        sa.Column("cost_per_video_second", sa.Float(), server_default="0.0"),
        sa.Column("cost_per_1k_input_tokens", sa.Float(), server_default="0.0"),
        sa.Column("cost_per_1k_output_tokens", sa.Float(), server_default="0.0"),
        sa.Column("tier_multipliers", sa.JSON(), server_default='{"fast": 0.2, "normal": 1.0, "hero": 2.5}'),
        sa.Column("active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # Seed default data
    op.execute("""
        INSERT INTO provider_cost_configs (id, provider, cost_per_image, cost_per_video_second, cost_per_1k_input_tokens, cost_per_1k_output_tokens, active)
        VALUES
            ('seed-doubao', 'doubao', 0.04, 0.30, 0.001, 0.002, true),
            ('seed-tongyi', 'tongyi', 0.08, 0.25, 0.002, 0.004, true),
            ('seed-comfyui', 'comfyui', 0.02, 0.15, 0.0, 0.0, true)
    """)


def downgrade() -> None:
    op.drop_table("provider_cost_configs")
