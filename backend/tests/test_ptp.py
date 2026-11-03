"""M10: promise-to-pay check - kept / partly kept / broken / escalated, once-only alert e-mails, currency, instalments, business date."""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app import ptp
from app.config import get_settings
from app.fx import RateTable
from app.models.ar import AuditLog, Job, OutboundMessage, PtpCommitment, RuleConfig
from tests.test_actions import headers  # noqa: F401  (cached login per test)
from tests.test_workbench import client, login_on, make_email, make_item  # noqa: F401  (fixtures + helpers)

PROMISE = date(2026, 11, 10)  # deadline = promise + 3 days = 13 Nov; broken from 14 Nov; escalated from 16 Nov


@pytest.fixture(autouse=True)
def fixed_rates(monkeypatch):
    rates = RateTable({"EUR": [(date(2026, 1, 1), Decimal("1.10"))], "GBP": [(date(2026, 1, 1), Decimal("1.25"))]}, {})
    monkeypatch.setattr(ptp, "get_rates", lambda db: rates)


def set_date(db, day: str):
    row = db.get(RuleConfig, "business_date")
    row.value = {"date": day}
    db.flush()


def promise(db, amount="100", currency="USD", day=PROMISE, instalment=1, invoice="INV9", **kw):
    e = make_email(db)
    w = make_item(db, e, line_type="PTP", final_classification="PTP", decision="AUTO_PROCESS", status="AUTO_PROCESSED",
                  invoice_ref_raw=invoice, invoice_ref_norm=invoice, kunnr="0000999999", amount=Decimal(amount) if amount else None,
                  currency=currency, **kw)
    c = PtpCommitment(work_item_id=w.id, kunnr=w.kunnr, bukrs="1000", instalment_no=instalment, promise_date=day,
                      amount=Decimal(amount) if amount else None, currency=currency, status="OPEN")
    db.add(c)
    db.flush()
    return c, w


def payment(db, amount="100", currency="USD", day=date(2026, 11, 9), invoice="INV9", status="PENDING_REVIEW", **kw):
    e = make_email(db, received_at=datetime(day.year, day.month, day.day, 9, tzinfo=timezone.utc))
    return make_item(db, e, line_type="REMITTANCE", final_classification="REMITTANCE", invoice_ref_raw=invoice,
                     invoice_ref_norm=invoice, kunnr="0000999999", amount=Decimal(amount) if amount else None, currency=currency,
                     payment_date=day, status=status, **kw)


def run(db):
    r = ptp.evaluate(db)
    return r


def status(db, c):
    db.refresh(c)
    return c.status


def mails(db, w):
    return list(db.scalars(select(OutboundMessage).where(OutboundMessage.work_item_id == w.id).order_by(OutboundMessage.id)))


# --------------------------------------------------------------------------- broken and escalated (the business date drives it)
def test_open_then_broken_then_escalated_with_one_email_each(db):
    c, w = promise(db)
    set_date(db, "2026-11-13")  # the last day of the grace period
    run(db)
    assert status(db, c) == "OPEN" and mails(db, w) == []
    set_date(db, "2026-11-14")
    r = run(db)
    assert status(db, c) == "BROKEN" and r.alerts >= 1
    m = mails(db, w)
    assert [x.kind for x in m] == ["ALERT"]
    assert m[0].subject.startswith("[AR-DEMO][ALERT → Collections]") and m[0].actual_recipient == get_settings().outbound_redirect_to
    assert m[0].intended_recipient == "collections@acme-demo.local" and "11 Nov" not in m[0].body and "2026-11-10" in m[0].body
    run(db)
    run(db)
    assert len(mails(db, w)) == 1  # never re-sent
    set_date(db, "2026-11-16")
    run(db)
    assert status(db, c) == "ESCALATED"
    assert [x.kind for x in mails(db, w)] == ["ALERT", "ESCALATION"]
    esc = mails(db, w)[1]
    assert esc.subject.startswith("[AR-DEMO][ESCALATION → AR Supervisor]") and esc.intended_recipient == "supervisor@acme-demo.local"
    run(db)
    assert len(mails(db, w)) == 2
    assert db.scalar(select(func.count()).select_from(Job).where(Job.job_type == "SEND_EMAIL", Job.payload["outbound_id"].astext == str(esc.id))) == 1
    acts = [a.action for a in db.scalars(select(AuditLog).where(AuditLog.entity_type == "ptp", AuditLog.entity_id == f"{w.entry_id}/1").order_by(AuditLog.id))]
    assert acts == ["PTP_BROKEN", "PTP_ESCALATED"]


def test_a_jump_straight_past_the_escalation_date_sends_both_once(db):
    c, w = promise(db)
    set_date(db, "2026-12-20")
    run(db)
    run(db)
    assert status(db, c) == "ESCALATED" and [x.kind for x in mails(db, w)] == ["ALERT", "ESCALATION"]


def test_moving_the_date_back_reopens_the_promise_but_never_resends(db):
    c, w = promise(db)
    set_date(db, "2026-11-20")
    run(db)
    set_date(db, "2026-11-05")
    run(db)
    assert status(db, c) == "OPEN"
    set_date(db, "2026-11-20")
    run(db)
    assert status(db, c) == "ESCALATED" and len(mails(db, w)) == 2


# --------------------------------------------------------------------------- paid
def test_payment_within_two_percent_keeps_the_promise(db):
    c, w = promise(db)
    payment(db, "98.50")  # 1.5 % short: inside the 2 % tolerance
    set_date(db, "2026-11-30")
    run(db)
    assert status(db, c) == "KEPT" and c.closed_at and c.amount_received == Decimal("98.50")
    assert mails(db, w) == [] and c.payments[0]["entry_id"]


def test_payment_in_part_is_partially_kept_and_raises_no_alert(db):
    c, w = promise(db)
    payment(db, "40")
    set_date(db, "2026-11-30")
    run(db)
    assert status(db, c) == "PARTIALLY_KEPT" and c.amount_received == Decimal("40") and mails(db, w) == []
    payment(db, "60", day=date(2026, 11, 11))  # the rest arrives
    run(db)
    assert status(db, c) == "KEPT"


def test_rejected_duplicate_and_late_payments_do_not_count(db):
    c, w = promise(db)
    payment(db, "100", status="REJECTED")
    payment(db, "100", status="DUPLICATE")
    payment(db, "100", day=date(2026, 11, 14))  # after the grace period (13 Nov)
    set_date(db, "2026-11-14")
    run(db)
    assert status(db, c) == "BROKEN"


def test_a_payment_dated_after_the_business_date_is_not_paid_yet(db):
    c, w = promise(db)
    payment(db, "100", day=date(2026, 11, 12))
    set_date(db, "2026-11-11")
    run(db)
    assert status(db, c) == "OPEN"
    set_date(db, "2026-11-12")  # "move the date forward" demo
    run(db)
    assert status(db, c) == "KEPT"


def test_payment_other_customer_or_other_invoice_does_not_count(db):
    c, w = promise(db)
    payment(db, "100", invoice="OTHER")
    other = payment(db, "100")
    other.kunnr = "0000111111"
    db.flush()
    set_date(db, "2026-11-14")
    run(db)
    assert status(db, c) == "BROKEN"


def test_payment_matched_by_open_item_counts_even_with_another_invoice_text(db):
    c, w = promise(db)
    c.bsid_id = 4242
    db.flush()
    payment(db, "100", invoice="INV-9 (ocr)", bsid_id=4242)
    set_date(db, "2026-11-12")
    run(db)
    assert status(db, c) == "KEPT"


def test_a_payment_without_an_amount_is_taken_as_paid_in_full_with_a_note(db):
    c, w = promise(db)
    payment(db, None, currency=None)
    set_date(db, "2026-11-12")
    run(db)
    assert status(db, c) == "KEPT" and "names no amount" in c.check_note


def test_rejecting_the_promise_record_cancels_it(db):
    c, w = promise(db)
    w.status = "REJECTED"
    db.flush()
    set_date(db, "2026-12-20")
    run(db)
    assert status(db, c) == "CANCELLED" and mails(db, w) == []


# --------------------------------------------------------------------------- currency
def test_a_payment_in_another_currency_is_converted_at_the_payment_date(db):
    c, w = promise(db, "100", "EUR")  # 100 EUR = 110 USD at 1.10
    payment(db, "110", "USD")
    set_date(db, "2026-11-12")
    run(db)
    assert status(db, c) == "KEPT" and c.amount_received == Decimal("100.00")
    c2, w2 = promise(db, "100", "EUR", invoice="INV8")
    payment(db, "100", "USD", invoice="INV8")  # worth only 90.91 EUR
    run(db)
    assert status(db, c2) == "PARTIALLY_KEPT" and c2.amount_received == Decimal("90.91")


def test_no_exchange_rate_keeps_the_promise_open_with_a_note_and_no_alert(db):
    c, w = promise(db, "100", "USD")
    payment(db, "100", "CHF")  # no rate for CHF in the table
    set_date(db, "2026-12-20")
    run(db)
    assert status(db, c) == "OPEN" and "cannot be converted" in c.check_note and mails(db, w) == []


# --------------------------------------------------------------------------- instalments
def test_instalments_are_filled_in_promise_date_order(db):
    first, w1 = promise(db, "100", day=date(2026, 11, 10), instalment=1)
    second, w2 = promise(db, "100", day=date(2026, 11, 20), instalment=2)
    payment(db, "150", day=date(2026, 11, 9))
    set_date(db, "2026-11-15")
    run(db)
    assert status(db, first) == "KEPT" and status(db, second) == "PARTIALLY_KEPT" and second.amount_received == Decimal("50")
    payment(db, "50", day=date(2026, 11, 18))
    run(db)
    assert status(db, second) == "PARTIALLY_KEPT"  # dated 18 Nov, the business date is still 15 Nov
    set_date(db, "2026-11-19")
    run(db)
    assert status(db, second) == "KEPT"


def test_one_payment_is_never_used_twice(db):
    first, w1 = promise(db, "100", day=date(2026, 11, 10), instalment=1)
    second, w2 = promise(db, "100", day=date(2026, 11, 20), instalment=2)
    payment(db, "100", day=date(2026, 11, 9))
    set_date(db, "2026-11-30")
    run(db)
    assert status(db, first) == "KEPT" and status(db, second) in ("ESCALATED", "BROKEN")


# --------------------------------------------------------------------------- API and worker
def test_ptp_api_lists_promises_and_run_rechecks_at_the_business_date(client, db):
    c, w = promise(db)
    h = headers(client)
    assert client.get("/api/ptp").status_code == 401 and client.post("/api/ptp/run").status_code == 401
    set_date(db, "2026-11-14")
    r = client.post("/api/ptp/run", headers=h).json()
    assert r["business_date"] == "2026-11-14" and f"{w.entry_id}/1: OPEN -> BROKEN" in r["changed"] and r["alerts"] >= 1
    assert client.post("/api/ptp/run", headers=h).json()["alerts"] == 0  # nothing new the second time
    body = client.get(f"/api/ptp?q={w.entry_id}", headers=h).json()
    item = body["items"][0]
    assert body["total"] == 1 and item["status"] == "BROKEN" and item["deadline"] == "2026-11-13" and item["days_overdue"] == 4
    assert item["alerted_at"] and item["escalated_at"] is None and body["counts"]["BROKEN"] >= 1 and body["grace_days"] == 3
    assert client.get("/api/ptp?status=KEPT&q=" + w.entry_id, headers=h).json()["total"] == 0
    a = db.scalar(select(AuditLog).where(AuditLog.entity_type == "ptp", AuditLog.action == "PTP_BROKEN", AuditLog.entity_id == f"{w.entry_id}/1"))
    assert a.actor == "analyst@acme-demo.local"


def test_the_worker_runs_the_check_and_reports_it(db):
    from app import worker

    c, w = promise(db)
    set_date(db, "2026-11-14")
    s = worker.RoundSummary()
    worker.ptp_checks(db, s)
    assert s.ptp_changed >= 1 and s.ptp_alerts >= 1 and "promises changed" in s.line()
