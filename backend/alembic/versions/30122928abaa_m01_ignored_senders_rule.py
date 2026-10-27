"""m01 ignored senders rule

Adds the rule "ignored_senders" to ar.rule_config if it is not there yet (an existing,
possibly edited, value is never overwritten). The value is written out here on purpose:
a migration must not change when app code changes later.

Revision ID: 30122928abaa
Revises: 282ef692a66c
Create Date: 2026-10-27 08:30:52.927494
"""
import json

from alembic import op
import sqlalchemy as sa


revision = '30122928abaa'
down_revision = '282ef692a66c'
branch_labels = None
depends_on = None

VALUE = {
    "domains": ["github.com", "google.com", "accounts.google.com", "microsoft.com", "azure.com",
                "anthropic.com", "claude.ai", "claude.com"],
    "patterns": ["no-reply@*", "noreply@*"],
}
DESCRIPTION = "System senders whose e-mails are NOT stored: only an audit entry and the Gmail label AR-Ignored."


def upgrade() -> None:
    op.get_bind().execute(
        sa.text("INSERT INTO ar.rule_config (key, value, description, updated_by) "
                "VALUES ('ignored_senders', CAST(:v AS jsonb), :d, 'migration') "
                "ON CONFLICT (key) DO NOTHING"),
        {"v": json.dumps(VALUE), "d": DESCRIPTION},
    )


def downgrade() -> None:
    op.execute("DELETE FROM ar.rule_config WHERE key = 'ignored_senders'")
