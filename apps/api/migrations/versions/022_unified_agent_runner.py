"""022 unified agent runner — B-1 Phase A schema additions

Adds:
- conversations.agent_state
- conversation_messages.trace_id, finish_reason
- conversation_actions.trace_id, skill_id  (job_id already exists as FK)
- skill_installations table
- mcp_server_connections table
- mcp_access_tokens table

SQLite-compatible via op.batch_alter_table (precedent: 003, b9a98c1685f5).

Revision ID: 022_unified_agent_runner
Revises: 021_panel_preview_key
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa


revision = "022_unified_agent_runner"
down_revision = "021_panel_preview_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. ALTER conversations
    with op.batch_alter_table("conversations") as batch:
        batch.add_column(
            sa.Column("agent_state", sa.String(16), nullable=False, server_default="idle")
        )

    # 2. ALTER conversation_messages
    with op.batch_alter_table("conversation_messages") as batch:
        batch.add_column(sa.Column("trace_id", sa.String(64), nullable=True))
        batch.add_column(sa.Column("finish_reason", sa.String(32), nullable=True))
        batch.create_index("idx_msg_trace_id", ["trace_id"])

    # 3. ALTER conversation_actions
    with op.batch_alter_table("conversation_actions") as batch:
        batch.add_column(sa.Column("trace_id", sa.String(64), nullable=True))
        batch.add_column(sa.Column("skill_id", sa.String(64), nullable=True))
        batch.create_index("idx_action_trace_id", ["trace_id"])
        batch.create_index("idx_action_skill_id", ["skill_id"])

    # 4. CREATE skill_installations
    op.create_table(
        "skill_installations",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("source_url", sa.String(512), nullable=True),
        sa.Column("install_path", sa.String(512), nullable=True),
        sa.Column("manifest_json", sa.JSON, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column("scope", sa.String(16), nullable=False, server_default="global"),
        sa.Column("project_id", sa.String, nullable=True),
        sa.Column("installed_at", sa.DateTime, nullable=False),
        sa.Column("last_loaded_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("name", "scope", "project_id", name="uq_skill_name_scope"),
    )
    op.create_index("idx_skill_name", "skill_installations", ["name"])
    op.create_index("idx_skill_project", "skill_installations", ["project_id"])
    op.create_index("idx_skill_status_scope", "skill_installations", ["status", "scope"])

    # 5. CREATE mcp_server_connections
    op.create_table(
        "mcp_server_connections",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("transport", sa.String(16), nullable=False),
        sa.Column("command", sa.String(512), nullable=True),
        sa.Column("args_json", sa.JSON, nullable=True),
        sa.Column("url", sa.String(512), nullable=True),
        sa.Column("env_json", sa.JSON, nullable=True),
        sa.Column("skill_id", sa.String, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="disconnected"),
        sa.Column("last_connected_at", sa.DateTime, nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("capabilities_json", sa.JSON, nullable=True),
        sa.Column("scope", sa.String(16), nullable=False, server_default="global"),
        sa.Column("project_id", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("idx_mcp_skill", "mcp_server_connections", ["skill_id"])
    op.create_index("idx_mcp_project", "mcp_server_connections", ["project_id"])
    op.create_index("idx_mcp_status", "mcp_server_connections", ["status"])

    # 6. CREATE mcp_access_tokens
    op.create_table(
        "mcp_access_tokens",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("user_id", sa.String, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("scopes_json", sa.JSON, nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=True),
        sa.Column("last_used_at", sa.DateTime, nullable=True),
        sa.Column("revoked_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("idx_mcp_token_hash", "mcp_access_tokens", ["token_hash"], unique=True)
    op.create_index("idx_mcp_token_user", "mcp_access_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_table("mcp_access_tokens")
    op.drop_table("mcp_server_connections")
    op.drop_table("skill_installations")

    with op.batch_alter_table("conversation_actions") as batch:
        batch.drop_index("idx_action_skill_id")
        batch.drop_index("idx_action_trace_id")
        batch.drop_column("skill_id")
        batch.drop_column("trace_id")

    with op.batch_alter_table("conversation_messages") as batch:
        batch.drop_index("idx_msg_trace_id")
        batch.drop_column("finish_reason")
        batch.drop_column("trace_id")

    with op.batch_alter_table("conversations") as batch:
        batch.drop_column("agent_state")
