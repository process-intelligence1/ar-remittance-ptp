"""Dashboard chart data (M08 follow-up): shared fixture with the front-end, the /api/kpis block, the trend date rule
and the SAP BSID Match block of the record detail."""
import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.charts import ChartInput, bucket_of, build_charts, period_key
from app.config import get_settings
from app.db import get_db
from app.main import app
from tests.test_workbench import login_on, client, headers, make_email, make_item  # noqa: F401  (fixtures + helpers)

FIXTURE = json.loads((Path(__file__).resolve().parents[2] / "data" / "eval" / "dashboard_charts_fixture.json").read_text(encoding="utf-8"))


def _items(rows):
    return [ChartInput(bucket_of(r["status"], r.get("resolved_by")), r["classification"], r["customer"], r["region"],
                       r["company_code"], date.fromisoformat(r["day"])) for r in rows]


def test_chart_data_matches_the_shared_fixture():
    assert build_charts(_items(FIXTURE["rows"])) == FIXTURE["expected"]


def test_periods_are_iso_weeks_and_calendar_months_and_quarters():
    assert period_key(date(2026, 12, 30), "week")[0] == "2026-W53"
    assert period_key(date(2027, 1, 3), "week")[0] == "2026-W53"      # Sunday still belongs to the week that started Monday
    assert period_key(date(2027, 1, 4), "week")[0] == "2027-W01"
    assert period_key(date(2026, 3, 31), "quarter") == ("2026-Q1", "2026 Q1")
    assert period_key(date(2026, 4, 1), "quarter")[0] == "2026-Q2"


def test_confirmed_rows_count_as_manual_and_duplicates_are_not_in_performance():
    assert bucket_of("CONFIRMED") == "manual" and bucket_of("IGNORED") is None
    perf = build_charts([ChartInput("duplicates", "DUPLICATE", "A", "R", "1000", date(2026, 1, 1))])["performance"]
    assert all(p["total"] == 0 for p in perf)


def test_kpis_endpoint_has_the_charts_and_trend_uses_the_email_date(client, db):
    e1 = make_email(db, received_at=datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc))
    h = make_email(db, source="history", business_date=date(2026, 8, 3), received_at=datetime(2026, 10, 30, tzinfo=timezone.utc))
    make_item(db, e1, status="AUTO_PROCESSED", decision="AUTO_PROCESS", payment_date=date(2026, 1, 1), region="EMEA")
    make_item(db, h, status="PENDING_REVIEW", payment_date=date(2026, 2, 2), region="EMEA")
    k = client.get("/api/kpis?customer=ZZTEST", headers=headers(client)).json()
    charts = k["charts"]
    assert charts["performance"][0] == {"label": "Remittance", "auto": 1, "manual": 1, "exceptions": 0, "total": 2}
    assert charts["dimensions"]["customer"][0]["label"] == "ZZTEST Corp" and charts["dimensions"]["customer"][0]["total"] == 2
    month = {m["key"]: m for m in charts["trend"]["month"]}
    assert set(month) == {"2026-10", "2026-08"}  # received date, and the BUSINESS date for the history e-mail - never the payment date
    assert month["2026-10"]["remittance"] == {"total": 1, "auto": 1} and month["2026-08"]["remittance"] == {"total": 1, "auto": 0}
    assert set(charts["trend"]) == {"date", "week", "month", "quarter"}


def test_record_detail_has_the_sap_bsid_match_block(client, db):
    item = db.execute(text("select b.id, b.xblnr, b.belnr, b.gjahr, b.buzei, b.kunnr, b.bukrs, b.waers, b.wrbtr, b.budat "
                           "from sap.bsid b join sap.kna1 k on k.kunnr = b.kunnr where b.xblnr is not null limit 1")).one()
    e = make_email(db)
    w = make_item(db, e, bsid_id=item.id, bsid_match_flag=True, bsid_open_item_status="OPEN", amount_difference_pct=Decimal("0.241"))
    d = client.get(f"/api/work-items/{w.entry_id}", headers=headers(client)).json()
    b = d["bsid"]
    assert b["matched"] is True and b["invoice"] == item.xblnr and b["document"] == item.belnr
    assert (b["fiscal_year"], b["item"], b["customer_no"], b["company_code"], b["currency"]) == (item.gjahr, item.buzei, item.kunnr, item.bukrs, item.waers)
    assert b["customer_name"] and b["posting_date"] == item.budat.isoformat() and b["open_item_status"] == "OPEN"
    assert float(b["amount_difference_pct"]) == 0.241
    w2 = make_item(db, e, bsid_match_flag=False)
    assert client.get(f"/api/work-items/{w2.entry_id}", headers=headers(client)).json()["bsid"] == {"matched": False}
