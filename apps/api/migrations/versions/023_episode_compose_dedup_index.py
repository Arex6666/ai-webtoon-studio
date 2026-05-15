"""023 episode_video_compose dedup index — Phase D

Adds a partial unique index on (project_id, inputs_json->>'episode_number')
where type='episode_video_compose' and status in ('queued','running','succeeded').
Failed rows are excluded so retries can create new compose jobs.

Postgres-only enforcement; SQLite test path uses an in-Python pre-check inside
_maybe_enqueue_episode_compose. Detect dialect to skip the index on SQLite,
which does not support partial indexes with JSON expressions.

Revision ID: 023_episode_compose_dedup
Revises: 022_unified_agent_runner
Create Date: 2026-05-11
"""
from alembic import op


revision = "023_episode_compose_dedup"
down_revision = "022_unified_agent_runner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite: no-op. The in-Python pre-check in compose_dispatch handles dedup.
        return
    op.execute(
        """
        CREATE UNIQUE INDEX uq_episode_compose_inflight
        ON jobs (project_id, ((inputs_json->>'episode_number')::int))
        WHERE type = 'episode_video_compose'
          AND status IN ('queued', 'running', 'succeeded')
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS uq_episode_compose_inflight")
