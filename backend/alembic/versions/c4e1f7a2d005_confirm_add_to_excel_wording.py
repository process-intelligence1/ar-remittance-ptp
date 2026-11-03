"""Action renamed: "Confirm & Extract to Excel" -> "Confirm & Add to Excel" (stored recommended_action text)

Revision ID: c4e1f7a2d005
Revises: b3d9e5f1c004
"""
from alembic import op

revision = 'c4e1f7a2d005'
down_revision = 'b3d9e5f1c004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE ar.work_item SET recommended_action = 'Confirm & Add to Excel' "
               "WHERE recommended_action IN ('Confirm & Extract to Excel', 'Confirm & Update SAP')")


def downgrade() -> None:
    op.execute("UPDATE ar.work_item SET recommended_action = 'Confirm & Extract to Excel' "
               "WHERE recommended_action = 'Confirm & Add to Excel'")
