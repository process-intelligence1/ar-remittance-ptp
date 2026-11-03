"""M09: row version (optimistic concurrency), confirm / export trail, outbound e-mail columns, reply link

Revision ID: d5f2a8b3e006
Revises: c4e1f7a2d005
"""
import sqlalchemy as sa
from alembic import op

revision = 'd5f2a8b3e006'
down_revision = 'c4e1f7a2d005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('work_item', sa.Column('row_version', sa.Integer(), server_default=sa.text('1'), nullable=False), schema='ar')
    op.add_column('work_item', sa.Column('confirmed_by', sa.String(120)), schema='ar')
    op.add_column('work_item', sa.Column('confirmed_at', sa.DateTime(timezone=True)), schema='ar')
    op.add_column('work_item', sa.Column('action_comment', sa.Text()), schema='ar')
    op.add_column('work_item', sa.Column('exported_at', sa.DateTime(timezone=True)), schema='ar')
    op.add_column('work_item', sa.Column('exported_by', sa.String(120)), schema='ar')
    op.create_index('ix_work_item_confirmed', 'work_item', ['status', 'confirmed_at'], schema='ar')
    # rows already confirmed (none expected) keep a sensible trail
    op.execute("UPDATE ar.work_item SET confirmed_at = coalesce(resolved_at, updated_at), confirmed_by = resolved_by "
               "WHERE status = 'CONFIRMED'")

    op.add_column('outbound_message', sa.Column('gmail_thread_id', sa.String(64)), schema='ar')
    op.add_column('outbound_message', sa.Column('language', sa.String(10)), schema='ar')
    op.add_column('outbound_message', sa.Column('template', sa.String(40)), schema='ar')
    op.add_column('outbound_message', sa.Column('error', sa.Text()), schema='ar')
    op.create_index('ix_outbound_thread', 'outbound_message', ['gmail_thread_id'], schema='ar')

    # a customer reply points at the e-mail it answers (same Gmail thread)
    op.add_column('email_message', sa.Column('parent_email_id', sa.BigInteger()), schema='ar')
    op.create_foreign_key('fk_email_parent', 'email_message', 'email_message', ['parent_email_id'], ['id'],
                          source_schema='ar', referent_schema='ar', ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_email_parent', 'email_message', schema='ar', type_='foreignkey')
    op.drop_column('email_message', 'parent_email_id', schema='ar')
    op.drop_index('ix_outbound_thread', table_name='outbound_message', schema='ar')
    for c in ('error', 'template', 'language', 'gmail_thread_id'):
        op.drop_column('outbound_message', c, schema='ar')
    op.drop_index('ix_work_item_confirmed', table_name='work_item', schema='ar')
    for c in ('exported_by', 'exported_at', 'action_comment', 'confirmed_at', 'confirmed_by', 'row_version'):
        op.drop_column('work_item', c, schema='ar')
