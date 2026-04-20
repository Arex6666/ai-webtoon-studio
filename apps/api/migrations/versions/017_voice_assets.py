"""Voice Assets - Add voice_agents and music_assets tables

Revision ID: 017_voice_assets
Revises: 016_enhance_qa
Create Date: 2026-03-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "017_voice_assets"
down_revision: Union[str, None] = "016_enhance_qa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Voice Agents table
    op.create_table(
        "voice_agents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("character_asset_id", sa.String(36), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("voice_id", sa.String(50), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False, server_default="doubao"),
        sa.Column("voice_config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("sample_audio_url", sa.String(512), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_voice_agents_project_id", "voice_agents", ["project_id"])
    op.create_index("ix_voice_agents_character_asset_id", "voice_agents", ["character_asset_id"])

    # Music Assets table
    op.create_table(
        "music_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("genre", sa.String(50), nullable=True),
        sa.Column("mood", sa.String(50), nullable=True),
        sa.Column("duration_sec", sa.Float(), nullable=True),
        sa.Column("audio_url", sa.String(512), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("generation_prompt", sa.Text(), nullable=True),
        sa.Column("generation_params", sa.JSON(), nullable=True),
        sa.Column("workflow_id", sa.String(100), nullable=True),
        sa.Column("job_id", sa.String(100), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="ready"),
        sa.Column("thumbnail_url", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_music_assets_project_id", "music_assets", ["project_id"])
    op.create_index("ix_music_assets_status", "music_assets", ["status"])


def downgrade() -> None:
    op.drop_table("music_assets")
    op.drop_table("voice_agents")
