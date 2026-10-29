"""Action renamed: "Confirm & Update SAP" -> "Confirm & Extract to Excel" (stored recommended_action text)

Revision ID: b3d9e5f1c004
Revises: a7c3d1e9b002
"""
from alembic import op

revision = 'b3d9e5f1c004'
down_revision = 'a7c3d1e9b002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE ar.work_item SET recommended_action = 'Confirm & Extract to Excel' "
               "WHERE recommended_action = 'Confirm & Update SAP'")


def downgrade() -> None:
    op.execute("UPDATE ar.work_item SET recommended_action = 'Confirm & Update SAP' "
               "WHERE recommended_action = 'Confirm & Extract to Excel'")
