"""Invoice-number matching rules (replaces "digit match length"): defaults, database rows, columns."""
import importlib.util
from pathlib import Path

from sqlalchemy import inspect, select

from app.db import engine
from app.models.ar import RuleConfig, WorkItem
from app.rules_defaults import DEFAULT_RULES, FAST_PATH_DESCRIPTION, INVOICE_MATCH

# load the migration file by path ("alembic" is also the name of the installed library)
_MIGRATION_FILE = Path(__file__).parents[1] / "alembic" / "versions" / "ba1d07b3363c_invoice_number_matching.py"
_spec = importlib.util.spec_from_file_location("migration_ba1d07b3363c", _MIGRATION_FILE)
migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration)


def test_defaults_describe_the_three_levels():
    levels = {lv["level"]: lv for lv in INVOICE_MATCH["levels"]}
    assert list(levels) == ["EXACT", "NEAR", "NONE"]
    assert (levels["EXACT"]["score"], levels["NEAR"]["score"], levels["NONE"]["score"]) == (1.00, 0.70, 0.00)
    assert levels["EXACT"]["fast_path_eligible"] is True
    assert levels["NEAR"]["max_char_differences"] == 1 and levels["NEAR"]["always_review"] is True
    assert levels["NEAR"]["reason"] == "Possible OCR misread"
    assert levels["NONE"]["decision"] == "EXCEPTION" and levels["NONE"]["reason"] == "No BSID match found"
    assert INVOICE_MATCH["primary_field"] == "XBLNR" and INVOICE_MATCH["alternate_fields"] == ["BELNR", "VBELN"]
    weights = DEFAULT_RULES["scoring_weights"][0]
    assert weights["invoice_match"] == 0.35 and "digit_evidence" not in weights
    assert round(sum(v for k, v in weights.items() if k != "normalization_max"), 2) == 0.90
    assert "digit_evidence_bands" not in DEFAULT_RULES
    assert DEFAULT_RULES["fast_path"][0]["required_match_level"] == "EXACT"


def test_migration_writes_the_same_values_as_the_defaults():
    assert migration.INVOICE_MATCH == INVOICE_MATCH
    assert migration.INVOICE_MATCH_DESCRIPTION == DEFAULT_RULES["invoice_match"][1]
    assert migration.FAST_PATH_DESCRIPTION == FAST_PATH_DESCRIPTION


def test_database_has_invoice_match_and_no_digit_rules(db):
    rows = {r.key: r for r in db.scalars(select(RuleConfig))}
    assert "digit_evidence_bands" not in rows
    assert rows["invoice_match"].value == INVOICE_MATCH
    assert rows["scoring_weights"].value["invoice_match"] == 0.35
    assert "digit_evidence" not in rows["scoring_weights"].value
    assert rows["fast_path"].value["required_match_level"] == "EXACT"
    assert not any("digit" in str(r.value).lower() or "digit" in (r.description or "").lower() for r in rows.values())


def test_work_item_columns():
    cols = {c["name"] for c in inspect(engine).get_columns("work_item", schema="ar")}
    assert {"match_field", "match_level", "invoice_match_score"} <= cols
    assert not {"digit_match_length", "digit_evidence_score"} & cols
    model_cols = set(WorkItem.__table__.columns.keys())
    assert {"match_field", "match_level", "invoice_match_score"} <= model_cols
    assert not {"digit_match_length", "digit_evidence_score"} & model_cols
