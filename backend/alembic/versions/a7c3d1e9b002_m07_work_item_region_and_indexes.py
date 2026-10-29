"""M07: work_item.region (BSID XREF2, kept after clearing) + indexes for the workbench queries

Revision ID: a7c3d1e9b002
Revises: fe8ac1f65174
"""
from alembic import op
import sqlalchemy as sa

revision = 'a7c3d1e9b002'
down_revision = 'fe8ac1f65174'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('work_item', sa.Column('region', sa.String(length=20), nullable=True), schema='ar')
    op.execute("UPDATE ar.work_item w SET region = b.xref2 FROM sap.bsid b WHERE w.bsid_id = b.id AND w.bsid_match_flag")
    for name, table, cols in (
        ('ix_work_item_email_id', 'work_item', ['email_id']),
        ('ix_work_item_bukrs', 'work_item', ['bukrs']),
        ('ix_work_item_region', 'work_item', ['region']),
        ('ix_work_item_updated_at', 'work_item', ['updated_at']),
        ('ix_work_item_created_at', 'work_item', ['created_at']),
        ('ix_audit_occurred_at', 'audit_log', ['occurred_at']),
        ('ix_audit_actor', 'audit_log', ['actor']),
    ):
        op.create_index(name, table, cols, schema='ar')


def downgrade() -> None:
    for name, table in (('ix_audit_actor', 'audit_log'), ('ix_audit_occurred_at', 'audit_log'),
                        ('ix_work_item_created_at', 'work_item'), ('ix_work_item_updated_at', 'work_item'),
                        ('ix_work_item_region', 'work_item'), ('ix_work_item_bukrs', 'work_item'),
                        ('ix_work_item_email_id', 'work_item')):
        op.drop_index(name, table_name=table, schema='ar')
    op.drop_column('work_item', 'region', schema='ar')
