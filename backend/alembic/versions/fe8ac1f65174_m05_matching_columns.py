"""m05 matching columns

ar.work_item gets: confidence_source (FAST_PATH | FORMULA) + formula_confidence (confidence =
max(fast-path value, formula)), review_reasons, the link to the extraction line, and how the customer
was identified (method, score, evidence). Sequence ar.entry_id_seq numbers the rows ENT-000001...
Rule "customer_identification" is added; rule "fast_path" records the max() rule. Existing (possibly
edited) values are never overwritten; values are written out here on purpose.

Revision ID: fe8ac1f65174
Revises: e975dc7e51e4
Create Date: 2026-10-27 23:09:52.337397
"""
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'fe8ac1f65174'
down_revision = 'e975dc7e51e4'
branch_labels = None
depends_on = None

CUSTOMER_IDENTIFICATION = {"name_similarity_min": 0.85, "cluster_min_history": 3}
CUSTOMER_IDENTIFICATION_DESCRIPTION = ("Customer identification (M05): payer-name similarity needed for a NAME match; "
                                       "history needed for payer / currency cluster flags (blank below it).")
FAST_PATH_DESCRIPTION = ("EXACT invoice match + BSID open + same currency + amount within tolerance -> 92%; "
                         "EXACT + amount missing -> 91%. Confidence = max(fast-path value, formula); the fast path "
                         "decides the category / decision.")


def upgrade() -> None:
    op.add_column('work_item', sa.Column('confidence_source', sa.String(length=12), nullable=True), schema='ar')
    op.add_column('work_item', sa.Column('formula_confidence', sa.Numeric(precision=5, scale=2), nullable=True), schema='ar')
    op.add_column('work_item', sa.Column('review_reasons', postgresql.JSONB(astext_type=sa.Text()), nullable=True), schema='ar')
    op.add_column('work_item', sa.Column('extraction_line_id', sa.BigInteger(), nullable=True), schema='ar')
    op.add_column('work_item', sa.Column('customer_match_method', sa.String(length=20), nullable=True), schema='ar')
    op.add_column('work_item', sa.Column('customer_match_score', sa.Numeric(precision=5, scale=4), nullable=True), schema='ar')
    op.add_column('work_item', sa.Column('customer_evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=True), schema='ar')
    op.create_foreign_key('fk_work_item_extraction_line', 'work_item', 'extraction_line', ['extraction_line_id'], ['id'],
                          source_schema='ar', referent_schema='ar', ondelete='SET NULL')
    op.execute("CREATE SEQUENCE IF NOT EXISTS ar.entry_id_seq")
    bind = op.get_bind()
    bind.execute(sa.text("INSERT INTO ar.rule_config (key, value, description, updated_by) "
                         "VALUES ('customer_identification', CAST(:v AS jsonb), :d, 'migration') "
                         "ON CONFLICT (key) DO NOTHING"),
                 {"v": json.dumps(CUSTOMER_IDENTIFICATION), "d": CUSTOMER_IDENTIFICATION_DESCRIPTION})
    # add the max() rule to the fast path - only the new key; edited thresholds stay as they are
    bind.execute(sa.text("UPDATE ar.rule_config SET value = value || CAST(:v AS jsonb), description = :d, "
                         "updated_by = 'migration' WHERE key = 'fast_path' AND NOT (value ? 'confidence')"),
                 {"v": json.dumps({"confidence": "max_of_fast_path_and_formula"}), "d": FAST_PATH_DESCRIPTION})


def downgrade() -> None:
    op.execute("UPDATE ar.rule_config SET value = value - 'confidence' WHERE key = 'fast_path'")
    op.execute("DELETE FROM ar.rule_config WHERE key = 'customer_identification'")
    op.execute("DROP SEQUENCE IF EXISTS ar.entry_id_seq")
    op.drop_constraint('fk_work_item_extraction_line', 'work_item', schema='ar', type_='foreignkey')
    op.drop_column('work_item', 'customer_evidence', schema='ar')
    op.drop_column('work_item', 'customer_match_score', schema='ar')
    op.drop_column('work_item', 'customer_match_method', schema='ar')
    op.drop_column('work_item', 'extraction_line_id', schema='ar')
    op.drop_column('work_item', 'review_reasons', schema='ar')
    op.drop_column('work_item', 'formula_confidence', schema='ar')
    op.drop_column('work_item', 'confidence_source', schema='ar')
