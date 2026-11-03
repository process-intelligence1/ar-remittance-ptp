"""M10: promise-to-pay check results (payments found, alert flags, notes)

Revision ID: e7a4b9c1f007
Revises: d5f2a8b3e006
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = 'e7a4b9c1f007'
down_revision = 'd5f2a8b3e006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('ptp_commitment', sa.Column('payments', JSONB()), schema='ar')
    op.add_column('ptp_commitment', sa.Column('broken_on', sa.Date()), schema='ar')
    op.add_column('ptp_commitment', sa.Column('alerted_at', sa.DateTime(timezone=True)), schema='ar')
    op.add_column('ptp_commitment', sa.Column('escalated_at', sa.DateTime(timezone=True)), schema='ar')
    op.add_column('ptp_commitment', sa.Column('check_note', sa.String(200)), schema='ar')
    op.add_column('ptp_commitment', sa.Column('last_checked_on', sa.Date()), schema='ar')


def downgrade() -> None:
    for c in ('last_checked_on', 'check_note', 'escalated_at', 'alerted_at', 'broken_on', 'payments'):
        op.drop_column('ptp_commitment', c, schema='ar')
