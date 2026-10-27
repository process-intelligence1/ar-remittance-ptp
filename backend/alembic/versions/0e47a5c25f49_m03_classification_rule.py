"""m03 classification rule

Adds the rule "classification" to ar.rule_config if it is not there yet (an existing, possibly
edited, value is never overwritten), and an index to find an e-mail's current classification.
The value is written out here on purpose: a migration must not change when app code changes later.

Revision ID: 0e47a5c25f49
Revises: 3fa92b553b2c
Create Date: 2026-10-27 13:26:45.550472
"""
import json

from alembic import op
import sqlalchemy as sa


revision = '0e47a5c25f49'
down_revision = '3fa92b553b2c'
branch_labels = None
depends_on = None

VALUE = {
    "contains_threshold": 3,
    "out_of_scope_threshold": 3,
    "evidence_bonus": 1,
    "known_sender_bonus": 1,
    "future_date_bonus": 1,
    "model_below_confidence": 70,
    "model_min_probability": 0.60,
    "model_min_chars": 25,
    "document_about_ar_categories": 3,
    "both_label": "PTP",
    "gmail_labels": {"REMITTANCE": "AR-Remittance", "PTP": "AR-PTP", "OUT_OF_SCOPE": "AR-OutOfScope"},
}
DESCRIPTION = ("E-mail classification (M03): keyword points needed for remittance / promise / out-of-scope, "
               "bonuses for invoice numbers, known senders and future dates, when the learned model is asked.")


def upgrade() -> None:
    op.get_bind().execute(
        sa.text("INSERT INTO ar.rule_config (key, value, description, updated_by) "
                "VALUES ('classification', CAST(:v AS jsonb), :d, 'migration') "
                "ON CONFLICT (key) DO NOTHING"),
        {"v": json.dumps(VALUE), "d": DESCRIPTION},
    )
    op.create_index("ix_email_classification_current", "email_classification", ["email_id", "is_current"],
                    schema="ar")


def downgrade() -> None:
    op.drop_index("ix_email_classification_current", table_name="email_classification", schema="ar")
    op.execute("DELETE FROM ar.rule_config WHERE key = 'classification'")
