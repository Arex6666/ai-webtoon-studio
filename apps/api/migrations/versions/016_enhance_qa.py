"""E5: Enhance qa_reports and fix_plans tables

Revision ID: 016_enhance_qa
Revises: 015_cost_config
Create Date: 2026-02-13

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "016_enhance_qa"
down_revision: Union[str, None] = "015_cost_config"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # QA Reports: add detailed issues and panel reference
    op.add_column("qa_reports", sa.Column("issues_json", sa.JSON(), nullable=True))
    op.add_column("qa_reports", sa.Column("panel_id", sa.String(36), nullable=True))

    # Fix Plans: add enhanced fields
    op.add_column("fix_plans", sa.Column("panel_id", sa.String(36), nullable=True))
    op.add_column("fix_plans", sa.Column("estimated_cost", sa.Float(), nullable=True))
    op.add_column("fix_plans", sa.Column("success_probability", sa.Float(), nullable=True))
    op.add_column("fix_plans", sa.Column("fix_type", sa.String(50), nullable=True))
    op.add_column("fix_plans", sa.Column("applied_by", sa.String(100), nullable=True))
    op.add_column("fix_plans", sa.Column("applied_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("fix_plans", "applied_at")
    op.drop_column("fix_plans", "applied_by")
    op.drop_column("fix_plans", "fix_type")
    op.drop_column("fix_plans", "success_probability")
    op.drop_column("fix_plans", "estimated_cost")
    op.drop_column("fix_plans", "panel_id")

    op.drop_column("qa_reports", "panel_id")
    op.drop_column("qa_reports", "issues_json")
