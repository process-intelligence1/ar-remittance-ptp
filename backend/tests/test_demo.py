"""M11: reset point and Reset demo, sample library and live set, Demo Control API, history rules (silent alerts, date override)."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text

from app import azure_jobs, demo, ptp
from app.api.auth import CurrentUser
from app.businessdate import current_business_date, override_business_date
from app.fx import RateTable
from app.gmail import sample_library
from app.models.ar import AuditLog, DemoSampleSent, EmailMessage, Job, OutboundMessage, PtpCommitment, RuleConfig, WorkItem
from tests.test_actions import ANALYST, act, headers  # noqa: F401  (cached login per test)
from tests.test_ptp import payment, promise, set_date  # noqa: F401
from tests.test_workbench import client, login_on, make_email, make_item  # noqa: F401  (fixtures + helpers)

USER = CurrentUser(email="analyst@acme-demo.local", name="Asha", role="AR_ANALYST")


@pytest.fixture(autouse=True)
def no_worker(monkeypatch):
    started = []
    monkeypatch.setattr(azure_jobs, "configured", lambda: True)
    monkeypatch.setattr(azure_jobs, "start_worker_job", lambda *a, **k: started.append(1) or "exec-1")
    monkeypatch.setattr(ptp, "get_rates", lambda db: RateTable({}, {}))
    return started


# --------------------------------------------------------------------------- the live set and the sample library
def test_the_live_set_has_one_sample_per_scenario_code_and_keeps_pairs_together():
    live = sample_library.live_set()
    lib = sample_library.get_library()
    codes = lib.codes()
    assert len(live) == 47 and len(set(live)) == 47 and set(live) <= set(codes)
    assert {c.split("-")[0] for c in live} == {c.split("-")[0] for c in codes}  # every scenario code is there
    assert {"P03-0193", "P03R-0194", "P05-0201", "P05R-0202"} <= set(live)  # promise and the payment that follows it
    history = sample_library.history_set()
    assert len(history) == 187 and not set(history) & set(live) and len(history) + len(live) == len(codes)
    assert history == sorted(history, key=lambda c: (int(c.split("-")[1]), c))


def test_a_storage_backed_library_reads_samples_like_the_local_one(tmp_path):
    from app.storage import LocalStorage

    store = LocalStorage(tmp_path)
    local = sample_library.LocalLibrary(sample_library.samples_root())
    code = "P03-0193"
    sample = local.load(code)
    store.put(f"samples/emails/{code}/body.txt", (sample_library.samples_root() / code / "body.txt").read_bytes())
    for a in sample.attachments:
        store.put(f"samples/emails/{code}/{a.name}", a.read_bytes())
    store.put("samples/live_set.txt", b"# comment\nP03-0193\n")
    lib = sample_library.StorageLibrary(store)
    assert lib.codes() == [code] and sample_library.live_set(lib) == [code] and sample_library.history_set(lib) == []
    again = lib.load(code)
    assert again.headers == sample.headers and again.body == sample.body
    assert [(a.name, a.read_bytes()) for a in again.attachments] == [(a.name, a.read_bytes()) for a in sample.attachments]
    with pytest.raises(FileNotFoundError):
        lib.load("R01-9999")


# --------------------------------------------------------------------------- reset point and Reset demo
def test_reset_restores_statuses_exports_promises_alerts_samples_sent_and_the_business_date(client, db):
    c, w = promise(db, day=date(2026, 11, 10))
    pending = make_item(db, make_email(db), status="PENDING_REVIEW", decision="MANUAL_REVIEW")
    done = make_item(db, make_email(db), status="AUTO_PROCESSED", decision="AUTO_PROCESS", invoice_ref_raw="D-1", invoice_ref_norm="D1",
                     amount=Decimal("10"), currency="USD")
    set_date(db, "2026-10-28")
    info = demo.take_reset_point(db, "tester")
    assert info["counts"]["ar.work_item"] >= 3 and info["business_date"] == "2026-10-28"
    h = headers(client)

    # the presenter plays with the demo ...
    assert act(client, done, "CONFIRM_ADD_EXCEL").status_code == 200                          # status + the exported-cases list
    assert client.post("/api/exports/cases/mark-exported", headers=h, json={}).json()["marked"] >= 1
    assert act(client, pending, "REJECT", comment="x").status_code == 200
    db.add(DemoSampleSent(code="R01-0001", sent_by="x"))                                     # sent-sample marker
    r = client.post("/api/demo/business-date", headers=h, json={"add_days": 30}).json()     # business date + promise status + alert flags
    assert r["business_date"] == "2026-11-27"
    db.refresh(c)
    assert c.status == "ESCALATED" and c.alerted_at and c.escalated_at
    db.flush()
    n_alerts = db.scalar(select(func.count()).select_from(OutboundMessage).where(OutboundMessage.work_item_id == w.id))
    assert n_alerts == 2

    # ... and Reset puts everything back
    res = client.post("/api/demo/reset", headers=h, json={"confirm": True})
    assert res.status_code == 200 and res.json()["business_date"] == "2026-10-28"
    db.expire_all()
    assert current_business_date(db) == date(2026, 10, 28)
    assert db.get(WorkItem, done.id).status == "AUTO_PROCESSED" and db.get(WorkItem, done.id).confirmed_at is None
    assert db.get(WorkItem, done.id).exported_at is None and db.get(WorkItem, pending.id).status == "PENDING_REVIEW"
    c2 = db.get(PtpCommitment, c.id)
    assert c2.status == "OPEN" and c2.alerted_at is None and c2.escalated_at is None
    assert db.scalar(select(func.count()).select_from(DemoSampleSent).where(DemoSampleSent.code == "R01-0001")) == 0
    assert db.scalar(select(func.count()).select_from(OutboundMessage).where(OutboundMessage.work_item_id == w.id)) == 0
    assert client.get("/api/exports/cases", headers=h).json()["count"] == 0 or all(i["entry_id"] != done.entry_id for i in client.get("/api/exports/cases", headers=h).json()["items"])
    reset_audit = db.scalar(select(AuditLog).where(AuditLog.action == "DEMO_RESET"))
    assert reset_audit.actor == ANALYST and reset_audit.details["restored_rows"]["work_item"] >= 3


def test_reset_never_reuses_entry_numbers_and_empties_the_job_queue(client, db):
    make_item(db, make_email(db))
    demo.take_reset_point(db, "tester")
    before = db.execute(text("select last_value from ar.entry_id_seq")).scalar()
    db.execute(text("select nextval('ar.entry_id_seq')"))
    db.add(Job(job_type="PROCESS_EMAIL", payload={"email_ref": "x"}))
    db.flush()
    demo.restore_reset_point(db, USER)
    assert db.execute(text("select last_value from ar.entry_id_seq")).scalar() > before  # not moved back
    assert db.scalar(select(func.count()).select_from(Job)) == 0


def test_reset_needs_a_reset_point_confirmation_and_no_running_job(client, db):
    h = headers(client)
    db.execute(text("drop schema if exists demo_reset cascade"))
    db.flush()
    assert client.post("/api/demo/reset", headers=h, json={"confirm": True}).status_code == 409   # no reset point yet
    demo.take_reset_point(db, "tester")
    assert client.post("/api/demo/reset", headers=h, json={}).status_code == 422                  # not confirmed
    db.add(Job(job_type="PROCESS_EMAIL", payload={}, status="RUNNING", started_at=datetime.now(timezone.utc)))
    db.flush()
    busy = client.post("/api/demo/reset", headers=h, json={"confirm": True})
    assert busy.status_code == 409 and "running" in busy.json()["detail"]
    assert client.post("/api/demo/reset", json={"confirm": True}).status_code == 401


def test_a_column_added_after_the_reset_point_gets_its_default_and_a_dropped_one_is_ignored(client, db):
    w = make_item(db, make_email(db))
    demo.take_reset_point(db, "tester")
    db.execute(text('alter table demo_reset."ar__work_item" drop column region'))        # "a column that was dropped later"
    db.execute(text('alter table demo_reset."ar__work_item" add column legacy_note text'))  # "...or exists only in the old copy"
    db.flush()
    demo.restore_reset_point(db, USER)
    assert db.get(WorkItem, w.id).entry_id == w.entry_id


# --------------------------------------------------------------------------- Demo Control API
def test_state_lists_the_live_set_and_what_was_sent(client, db):
    h = headers(client)
    demo.take_reset_point(db, "tester")
    s = client.get("/api/demo/state", headers=h).json()
    assert len(s["live_set"]) == 47 and s["reset_point"]["counts"]["ar.work_item"] >= 0 and s["sent_total"] == 0
    p03 = next(x for x in s["live_set"] if x["code"] == "P03-0193")
    assert p03["subject"] and p03["from"] and p03["attachments"] and p03["sent_count"] == 0
    assert client.get("/api/demo/state").status_code == 401


def test_send_sample_imports_into_gmail_marks_it_and_starts_the_worker(client, db, fake_service, monkeypatch, no_worker):
    from app.gmail import client as gmail_client

    monkeypatch.setattr(gmail_client, "build_service", lambda *a, **k: fake_service)
    h = headers(client)
    r = client.post("/api/demo/send-sample", headers=h, json={"code": "P03-0193"})
    assert r.status_code == 200 and r.json()["subject"] and r.json()["worker"]["started"] is True and no_worker == [1]
    msgs = list(fake_service.gmail.messages.values())
    assert len(msgs) == 1 and b"X-AR-Sample: P03-0193" in __import__("base64").urlsafe_b64decode(msgs[0]["raw"])
    again = client.post("/api/demo/send-sample", headers=h, json={"code": "P03-0193", "process_now": False}).json()
    assert again["worker"] is None
    row = next(x for x in client.get("/api/demo/state", headers=h).json()["live_set"] if x["code"] == "P03-0193")
    assert row["sent_count"] == 2 and row["last_sent_by"] == ANALYST
    assert client.post("/api/demo/send-sample", headers=h, json={"code": "R01-0002"}).status_code == 422   # a history sample, not live
    assert client.post("/api/demo/send-sample", headers=h, json={"code": "NOPE-0000"}).status_code == 422
    assert db.scalar(select(AuditLog).where(AuditLog.action == "DEMO_SAMPLE_SENT", AuditLog.entity_id == "P03-0193"))


def test_business_date_can_be_set_or_moved_and_checks_the_promises(client, db, no_worker):
    h = headers(client)
    set_date(db, "2026-10-28")
    c, w = promise(db, day=date(2026, 11, 10))
    r = client.post("/api/demo/business-date", headers=h, json={"add_days": 17}).json()
    assert r["before"] == "2026-10-28" and r["business_date"] == "2026-11-14" and r["ptp"]["alerts"] >= 1 and r["worker"]["started"] is True
    assert client.post("/api/demo/business-date", headers=h, json={"date": "2026-10-28"}).json()["business_date"] == "2026-10-28"
    assert client.post("/api/demo/business-date", headers=h, json={}).status_code == 422
    assert client.post("/api/demo/business-date", headers=h, json={"date": "2026-10-28", "add_days": 1}).status_code == 422
    assert client.post("/api/demo/business-date", headers=h, json={"date": "1999-01-01"}).status_code == 422
    assert client.get("/api/settings/business-date").json()["business_date"] == "2026-10-28"


def test_process_now_for_a_signed_in_user(client, no_worker):
    assert client.post("/api/demo/process-now", headers=headers(client)).json()["started"] is True and no_worker == [1]
    assert client.post("/api/demo/process-now").status_code == 401


# --------------------------------------------------------------------------- history rules
def test_history_emails_never_send_alert_mails_but_their_promises_are_flagged(db):
    c, w = promise(db)
    db.get(EmailMessage, w.email_id).source = "history"
    db.flush()
    set_date(db, "2026-12-20")
    ptp.evaluate(db)
    db.refresh(c)
    assert c.status == "ESCALATED" and c.alerted_at and c.escalated_at           # flagged ...
    assert db.scalar(select(func.count()).select_from(OutboundMessage).where(OutboundMessage.work_item_id == w.id)) == 0  # ... but no mail


def test_the_business_date_override_is_local_to_the_block(db):
    set_date(db, "2026-10-28")
    with override_business_date(date(2026, 8, 3)):
        assert current_business_date(db) == date(2026, 8, 3)
    assert current_business_date(db) == date(2026, 10, 28)


def test_the_worker_does_not_pick_up_history_emails(db):
    from app import worker

    e = make_email(db, source="history")
    e.status = "NEW"
    other = make_email(db)
    other.status = "NEW"
    db.flush()
    worker.queue_unfinished(db)
    queued = {j.payload["email_ref"] for j in db.scalars(select(Job).where(Job.job_type == "PROCESS_EMAIL"))}
    assert other.email_ref in queued and e.email_ref not in queued


def test_a_history_clarification_is_stored_as_already_sent_without_a_job(client, db):
    from app import actions

    w = make_item(db, make_email(db), decision="MANUAL_REVIEW", status="PENDING_REVIEW")
    actions.apply_action(actions.Context(db, history=True), USER, w, "REQUEST_CLARIFICATION", version=w.row_version,
                         email={"subject": "[AR-DEMO][CLARIFICATION → x] s", "body": "b"}, commit=False)
    m = db.scalar(select(OutboundMessage).where(OutboundMessage.work_item_id == w.id))
    assert m.status == "SENT" and m.sent_at and w.status == "AWAITING_CUSTOMER"
    assert db.scalar(select(func.count()).select_from(Job).where(Job.job_type == "SEND_EMAIL", Job.payload["outbound_id"].astext == str(m.id))) == 0


# --------------------------------------------------------------------------- building the history
def test_history_dates_spread_over_three_months_on_working_days_in_order():
    from app import history

    bd = date(2026, 10, 28)
    ds = history.spread_dates(187, bd)
    assert len(ds) == 187 and ds == sorted(ds) and all(d.weekday() < 5 for d in ds)
    assert ds[0] <= date(2026, 7, 31) and ds[-1] == date(2026, 10, 27) and (bd - ds[0]).days <= 95
    assert history.received_at(ds[3], "R01-0002") == history.received_at(ds[3], "R01-0002")  # deterministic
    assert history.spread_dates(1, bd)[0] < bd


def test_history_build_stores_emails_in_the_past_skips_what_exists_and_survives_a_failure(db, tmp_path):
    from app import history
    from app.storage import LocalStorage

    from sqlalchemy import delete

    lib = sample_library.get_library()
    codes = ["R01-0002", "R01-0003", "R01-0004", "R01-0005", "R01-0006"]
    db.execute(delete(EmailMessage).where(EmailMessage.source == "history", EmailMessage.sample_code.in_(codes)))  # rolled back with the test
    db.flush()
    codes, extra = codes[:3], codes[3:]
    bd = date(2026, 10, 28)
    seen = []

    def fake_process(db_, email, last_attempt=False):
        seen.append((email.sample_code, current_business_date(db_)))
        if email.sample_code == "R01-0003":
            raise RuntimeError("boom")

    stats = history.build_emails(db, codes, lib, bd, process=fake_process, storage=LocalStorage(tmp_path))
    assert (stats.built, stats.skipped, len(stats.failed)) == (2, 0, 1) and "R01-0003" in stats.failed[0]
    mails = {e.sample_code: e for e in db.scalars(select(EmailMessage).where(EmailMessage.source == "history", EmailMessage.sample_code.in_(codes)))}
    assert set(mails) == {"R01-0002", "R01-0003", "R01-0004"}  # the failed one stays stored; the next run continues with its stages
    dates = dict(zip(codes, history.spread_dates(3, bd)))
    for code, e in mails.items():
        assert e.received_at.date() == dates[code] and e.business_date == dates[code] and e.received_at.date() < bd
    assert [d for _, d in seen] == [dates[c] for c, _ in seen]            # the pipeline saw the e-mail's own business date ...
    assert current_business_date(db) == date(2026, 10, 28)               # ... and only inside the block
    again = history.build_emails(db, codes, lib, bd, process=fake_process, storage=LocalStorage(tmp_path))
    assert (again.built, again.skipped) == (0, 3)
    assert history.build_emails(db, extra, lib, bd, process=lambda *a, **k: None, limit=1, storage=LocalStorage(tmp_path)).built == 1


def test_history_moves_promise_and_payment_dates_with_the_email(db):
    from app import history

    c, w = promise(db, day=date(2026, 11, 27))
    w.payment_date = date(2026, 11, 20)
    db.flush()
    e = db.get(EmailMessage, w.email_id)
    history.shift_dates(db, e, -85)
    db.refresh(c)
    db.refresh(w)
    assert c.promise_date == date(2026, 9, 3) and w.promise_date is None or w.promise_date == date(2026, 9, 3)
    assert w.payment_date == date(2026, 8, 27)
    history.shift_dates(db, e, 0)  # no change
    db.refresh(c)
    assert c.promise_date == date(2026, 9, 3)


@pytest.mark.parametrize("decision,status,assigned", [("AUTO_PROCESS", "AUTO_PROCESSED", "CASH_APPLICATION"), ("MANUAL_REVIEW", "PENDING_REVIEW", "CASH_APPLICATION"),
                                                      ("EXCEPTION", "EXCEPTION", "AR_ANALYST"), ("DUPLICATE", "DUPLICATE", "AR_ANALYST"),
                                                      ("MANUAL_INVESTIGATION", "PENDING_REVIEW", "AR_ANALYST")])
def test_every_decision_gets_a_user_action_trail_with_past_timestamps(db, decision, status, assigned):
    from app import history

    users = history.load_users(db)
    bd = date(2026, 10, 28)
    for n in range(12):  # several rows per decision: different dice rolls, never an untouched row
        e = make_email(db, source="history", received_at=datetime(2026, 8, 3, 9, tzinfo=timezone.utc))
        e.sample_code = f"R99-{n:04d}"
        w = make_item(db, e, decision=decision, status=status, assigned_role=assigned, invoice_ref_raw="H-1", invoice_ref_norm="H1",
                      amount=Decimal("5"), currency="USD", match_level="EXACT")
        stats = history.ActionStats()
        history.Player(db, bd, users, stats).work(w, e)
        db.refresh(w)
        assert stats.actions >= 1 and w.status != status or decision == "AUTO_PROCESS" and w.status == "CONFIRMED" or w.status != status
        trail = list(db.scalars(select(AuditLog).where(AuditLog.entity_id == w.entry_id, AuditLog.actor != "system")))
        assert trail, f"{decision}: no user action"
        assert all(a.occurred_at > e.received_at and a.occurred_at.date() <= bd and a.business_date <= bd for a in trail)
        assert w.confirmed_at is None or w.confirmed_at.date() <= bd
    # a history clarification is stored as sent and never queued
    assert db.scalar(select(func.count()).select_from(Job).where(Job.job_type == "SEND_EMAIL")) == 0


def test_pipeline_audit_entries_move_to_the_emails_own_time_before_the_user_actions(db):
    from app import history

    e = make_email(db, source="history", received_at=datetime(2026, 8, 3, 9, 30, tzinfo=timezone.utc))
    e.business_date = date(2026, 8, 3)
    w = make_item(db, e)
    now = datetime.now(timezone.utc)
    for action, kind, ident in (("EMAIL_INGESTED", "email", e.email_ref), ("EMAIL_PARSED", "email", e.email_ref), ("WORK_ITEMS_CREATED", "work_item", w.entry_id)):
        db.add(AuditLog(actor="system", entity_type=kind, entity_id=ident, action=action, occurred_at=now, business_date=date(2026, 11, 3)))
    db.add(AuditLog(actor="x@acme-demo.local", entity_type="work_item", entity_id=w.entry_id, action="CONFIRM_ADD_EXCEL", occurred_at=now))
    db.flush()
    assert history.stamp_pipeline(db, e) == 3
    rows = list(db.scalars(select(AuditLog).where(AuditLog.entity_id.in_([e.email_ref, w.entry_id])).order_by(AuditLog.id)))
    system = [a for a in rows if a.actor == "system"]
    assert [a.occurred_at for a in system] == sorted(a.occurred_at for a in system)
    assert all(e.received_at < a.occurred_at < e.received_at + timedelta(minutes=2) and a.business_date == date(2026, 8, 3) for a in system)
    assert rows[-1].actor != "system" and rows[-1].occurred_at == now  # a person's entry is never touched
    db.refresh(w)
    assert w.created_at == system[-1].occurred_at + timedelta(seconds=20)
    first = [a.occurred_at for a in system]
    assert history.stamp_pipeline(db, e) == 3 and [a.occurred_at for a in system] == first  # repeating gives the same times
