"""
Merge migration branches
Merges 003_add_asset_reference_fields and 008_add_conversation_models
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '009_merge_branches'
down_revision = ('003_add_asset_reference_fields', '008_add_conversation_models')
branch_labels = None
depends_on = None


def upgrade():
    # No changes needed - this is just a merge point
    pass


def downgrade():
    # No changes needed - this is just a merge point
    pass
