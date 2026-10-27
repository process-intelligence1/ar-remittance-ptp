"""ignored senders: domains only

Removes the address patterns (no-reply@*, noreply@*) from rule "ignored_senders": automated
senders can send genuine remittances (sample R19-0112: noreply@kangaroo-erp-mail.net). Only the
"patterns" key and the description change; the domain list (and any edits to it) is kept.

Revision ID: 3fa92b553b2c
Revises: ede1408ffb5c
Create Date: 2026-10-27 12:20:41.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '3fa92b553b2c'
down_revision = 'ede1408ffb5c'
branch_labels = None
depends_on = None

DESCRIPTION = ("System sender DOMAINS (incl. sub-domains) whose e-mails are NOT stored: only an audit entry and the "
               "Gmail label AR-Ignored. No address patterns - automated senders can send genuine remittances.")
OLD_DESCRIPTION = "System senders whose e-mails are NOT stored: only an audit entry and the Gmail label AR-Ignored."


def upgrade() -> None:
    op.get_bind().execute(sa.text(
        "UPDATE ar.rule_config SET value = value - 'patterns', description = :d, updated_by = 'migration', "
        "updated_at = now() WHERE key = 'ignored_senders'"), {"d": DESCRIPTION})


def downgrade() -> None:
    op.get_bind().execute(sa.text(
        "UPDATE ar.rule_config SET value = value || '{\"patterns\": [\"no-reply@*\", \"noreply@*\"]}'::jsonb, "
        "description = :d WHERE key = 'ignored_senders'"), {"d": OLD_DESCRIPTION})
