"""M11: demo control - the schema that holds the reset point, and the sent-sample markers

Revision ID: f8b5c2d0a008
Revises: e7a4b9c1f007

The tables inside demo_reset are created and refreshed by the application (app/demo.py take_reset_point), because they are
copies of whatever ar.* looks like at that moment.
"""
import sqlalchemy as sa
from alembic import op

revision = 'f8b5c2d0a008'
down_revision = 'e7a4b9c1f007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS demo_reset")
    op.create_table(
        'demo_sample_sent',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('code', sa.String(20), nullable=False),
        sa.Column('sent_by', sa.String(120), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('gmail_id', sa.String(64)),
        schema='ar',
    )
    op.create_index('ix_demo_sample_code', 'demo_sample_sent', ['code'], schema='ar')


def downgrade() -> None:
    op.drop_index('ix_demo_sample_code', table_name='demo_sample_sent', schema='ar')
    op.drop_table('demo_sample_sent', schema='ar')
    op.execute("DROP SCHEMA IF EXISTS demo_reset CASCADE")
