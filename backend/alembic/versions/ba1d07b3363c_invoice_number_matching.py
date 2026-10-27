"""invoice number matching

Replaces the prototype's "digit match length" with invoice-number matching (see BUILD_PLAN M05).

ar.work_item
  digit_match_length    -> dropped; new match_field (XBLNR/BELNR/VBELN) + match_level (EXACT/NEAR/NONE)
  digit_evidence_score  -> renamed invoice_match_score
ar.rule_config (ONLY these keys; every other rule is left as it is)
  digit_evidence_bands  -> deleted; new key invoice_match
  scoring_weights       -> key "digit_evidence" renamed "invoice_match" (value and other weights kept)
  fast_path             -> adds required_match_level = EXACT, new description

Values are written out here on purpose: a migration must not change when app code changes later.

Revision ID: ba1d07b3363c
Revises: 30122928abaa
Create Date: 2026-10-27 10:05:12.000000
"""
import json

from alembic import op
import sqlalchemy as sa


revision = 'ba1d07b3363c'
down_revision = '30122928abaa'
branch_labels = None
depends_on = None

INVOICE_MATCH = {
    "primary_field": "XBLNR",
    "alternate_fields": ["BELNR", "VBELN"],
    "normalisation": {"upper_case": True, "remove_spaces": True, "remove_separators": ["-", "/", "."],
                      "strip_leading_zeros": True},
    "levels": [
        {"level": "EXACT", "score": 1.00, "fast_path_eligible": True,
         "label": "Identical, or identical after normalisation"},
        {"level": "NEAR", "score": 0.70, "max_char_differences": 1,
         "ocr_confusions": [["0", "O"], ["1", "I", "L"], ["5", "S"], ["8", "B"], ["2", "Z"]],
         "always_review": True, "reason": "Possible OCR misread",
         "label": "Exactly one character differs and it is a common OCR confusion"},
        {"level": "NONE", "score": 0.00, "decision": "EXCEPTION", "reason": "No BSID match found",
         "label": "No invoice-number match"},
    ],
}
INVOICE_MATCH_DESCRIPTION = (
    "Invoice-number match against BSID: XBLNR primary, BELNR/VBELN exact-only alternates. "
    "EXACT 1.00, NEAR (one OCR-confusable character) 0.70 always review, NONE 0.00 = exception."
)
FAST_PATH_DESCRIPTION = ("EXACT invoice match + BSID open + same currency + amount within tolerance = 92%; "
                         "EXACT + amount missing = 91% (sets confidence directly).")

OLD_DIGIT_BANDS = {"bands": [{"min_digits": 10, "score": 1.00, "label": "Exact 10-digit match"},
                             {"min_digits": 8, "score": 0.90, "label": "Strong partial match"},
                             {"min_digits": 7, "score": 0.82, "label": "Partial match"},
                             {"min_digits": 6, "score": 0.70, "label": "Weak partial match"},
                             {"min_digits": 0, "score": 0.00, "label": "No reliable match"}]}
OLD_DIGIT_DESCRIPTION = "Score for how many invoice digits / reference characters match the BSID item."
OLD_FAST_PATH_DESCRIPTION = ("Exact 10-digit invoice + BSID + same currency (+ amount within tolerance) "
                             "sets confidence directly.")


def _exec(sql: str, **params) -> None:
    op.get_bind().execute(sa.text(sql), params)


def upgrade() -> None:
    # --- ar.work_item columns (table has no rows yet; rename keeps any score values) ---
    op.alter_column('work_item', 'digit_evidence_score', new_column_name='invoice_match_score', schema='ar')
    op.drop_column('work_item', 'digit_match_length', schema='ar')
    op.add_column('work_item', sa.Column('match_field', sa.String(length=10), nullable=True), schema='ar')
    op.add_column('work_item', sa.Column('match_level', sa.String(length=10), nullable=True), schema='ar')

    # --- ar.rule_config: only the changed keys ---
    _exec("INSERT INTO ar.rule_config (key, value, description, updated_by) "
          "VALUES ('invoice_match', CAST(:v AS jsonb), :d, 'migration') ON CONFLICT (key) DO NOTHING",
          v=json.dumps(INVOICE_MATCH), d=INVOICE_MATCH_DESCRIPTION)
    _exec("DELETE FROM ar.rule_config WHERE key = 'digit_evidence_bands'")
    _exec("UPDATE ar.rule_config "
          "SET value = (value - 'digit_evidence') || jsonb_build_object('invoice_match', value -> 'digit_evidence'), "
          "    updated_by = 'migration', updated_at = now() "
          "WHERE key = 'scoring_weights' AND jsonb_exists(value, 'digit_evidence')")
    _exec("UPDATE ar.rule_config "
          "SET value = value || jsonb_build_object('required_match_level', 'EXACT'), description = :d, "
          "    updated_by = 'migration', updated_at = now() "
          "WHERE key = 'fast_path'", d=FAST_PATH_DESCRIPTION)


def downgrade() -> None:
    _exec("UPDATE ar.rule_config SET value = value - 'required_match_level', description = :d WHERE key = 'fast_path'",
          d=OLD_FAST_PATH_DESCRIPTION)
    _exec("UPDATE ar.rule_config "
          "SET value = (value - 'invoice_match') || jsonb_build_object('digit_evidence', value -> 'invoice_match') "
          "WHERE key = 'scoring_weights' AND jsonb_exists(value, 'invoice_match')")
    _exec("INSERT INTO ar.rule_config (key, value, description, updated_by) "
          "VALUES ('digit_evidence_bands', CAST(:v AS jsonb), :d, 'migration') ON CONFLICT (key) DO NOTHING",
          v=json.dumps(OLD_DIGIT_BANDS), d=OLD_DIGIT_DESCRIPTION)
    _exec("DELETE FROM ar.rule_config WHERE key = 'invoice_match'")

    op.drop_column('work_item', 'match_level', schema='ar')
    op.drop_column('work_item', 'match_field', schema='ar')
    op.add_column('work_item', sa.Column('digit_match_length', sa.Integer(), nullable=True), schema='ar')
    op.alter_column('work_item', 'invoice_match_score', new_column_name='digit_evidence_score', schema='ar')
