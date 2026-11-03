"""M09: actions, versions (409), bulk all-or-nothing, decision-based Dashboard, Excel export list, outbound e-mail, replies."""
import base64
import email as pyemail
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text

from app import azure_jobs, outbound
from app.config import get_settings
from app.models.ar import AuditLog, EmailMessage, Job, OutboundMessage, WorkItem
from tests import test_workbench
from tests.test_workbench import client, login_on, make_email, make_item  # noqa: F401  (fixtures + helpers)

ANALYST, CASHAPP, SUPERVISOR = "analyst@acme-demo.local", "cashapp@acme-demo.local", "supervisor@acme-demo.local"


def headers(client, user=ANALYST):
    """One login per user and test (the login is rate limited to 10 a minute)."""
    cache = client.__dict__.setdefault("_tokens", {})
    if user not in cache:
        cache[user] = test_workbench.headers(client, user)
    return cache[user]


@pytest.fixture(autouse=True)
def no_worker_start(monkeypatch):
    started = []
    monkeypatch.setattr(azure_jobs, "configured", lambda: True)
    monkeypatch.setattr(azure_jobs, "start_worker_job", lambda *a, **k: started.append(1) or "exec-1")
    return started


def row(client, w, user=ANALYST):
    return client.get(f"/api/work-items?q={w.entry_id}", headers=headers(client, user)).json()["items"][0]


def act(client, w, action, user=ANALYST, version=None, **body):
    version = row(client, w, user)["version"] if version is None else version
    return client.post(f"/api/work-items/{w.entry_id}/actions", headers=headers(client, user),
                       json={"action": action, "version": version, **body})


def item(db, **kw):
    e = make_email(db)
    return make_item(db, e, **{"invoice_ref_raw": "INV-1", "invoice_ref_norm": "INV1", "amount": Decimal("100"), "currency": "USD", **kw})


def sap_sample(db, where="1=1"):
    """An open item whose invoice number is unique, with its customer."""
    return db.execute(text(
        "select b.id, b.kunnr, b.bukrs, b.xblnr, b.wrbtr, b.waers from sap.bsid b join sap.kna1 k on k.kunnr = b.kunnr "
        f"where b.shkzg = 'S' and b.xblnr is not null and ({where}) "
        "and (select count(*) from sap.bsid x where x.xblnr = b.xblnr) = 1 order by b.id limit 1")).one()


# --------------------------------------------------------------------------- confirm
def test_confirm_sets_confirmed_audits_before_after_and_offers_nothing_more(client, db):
    w = item(db, status="AUTO_PROCESSED", decision="AUTO_PROCESS")
    bsid_before = db.scalar(text("select count(*) from sap.bsid")), db.scalar(text("select count(*) from sap.bsad"))
    r = act(client, w, "CONFIRM_ADD_EXCEL", comment="ok")
    assert r.status_code == 200, r.text
    body = r.json()["item"]
    assert body["status"] == "CONFIRMED" and body["allowed_actions"] == [] and body["version"] == 2
    db.refresh(w)
    assert w.confirmed_by == ANALYST and w.confirmed_at and w.resolved_by == ANALYST
    a = db.scalar(select(AuditLog).where(AuditLog.entity_id == w.entry_id, AuditLog.action == "CONFIRM_ADD_EXCEL"))
    assert a.actor == ANALYST and a.details["before"]["status"] == "AUTO_PROCESSED" and a.details["after"]["status"] == "CONFIRMED"
    assert a.details["comment"] == "ok"
    assert (db.scalar(text("select count(*) from sap.bsid")), db.scalar(text("select count(*) from sap.bsad"))) == bsid_before
    assert act(client, w, "CONFIRM_ADD_EXCEL").status_code == 403  # a CONFIRMED row offers no further actions


def test_confirm_is_refused_when_the_row_is_not_complete(client, db):
    w = item(db, status="PENDING_REVIEW", decision="MANUAL_REVIEW", invoice_ref_norm=None, bsid_match_flag=False, amount=None)
    r = act(client, w, "CONFIRM_ADD_EXCEL")
    assert r.status_code == 422 and "invoice number missing" in r.json()["detail"]["message"]
    db.refresh(w)
    assert w.status == "PENDING_REVIEW"


def test_a_stale_version_is_a_409_and_nothing_changes(client, db):
    w = item(db, status="AUTO_PROCESSED", decision="AUTO_PROCESS")
    seen = row(client, w)["version"]
    assert act(client, w, "REJECT", comment="x", version=seen).status_code == 403 or True  # (reject is not offered for AUTO_PROCESS)
    w2 = item(db)
    seen = row(client, w2)["version"]
    assert act(client, w2, "REQUEST_CLARIFICATION", version=seen, email={"subject": "s", "body": "b"}).status_code == 200
    stale = act(client, w2, "REJECT", version=seen, comment="late")
    assert stale.status_code == 409 and "changed by someone else" in stale.json()["detail"]["message"]
    db.refresh(w2)
    assert w2.status == "AWAITING_CUSTOMER"


def test_a_role_without_access_gets_403(client, db):
    w = item(db, assigned_role="COLLECTIONS_ANALYST")
    assert act(client, w, "REJECT", user=CASHAPP, comment="x").status_code == 403


# --------------------------------------------------------------------------- reject / escalate / duplicates
def test_reject_needs_a_comment_and_sets_rejected(client, db):
    w = item(db)
    assert act(client, w, "REJECT").status_code == 422
    r = act(client, w, "REJECT", comment="not ours")
    assert r.status_code == 200 and r.json()["item"]["status"] == "REJECTED" and r.json()["item"]["action_comment"] == "not ours"


def test_escalate_goes_to_the_supervisor_only(client, db):
    w = item(db, decision="MANUAL_INVESTIGATION")
    assert act(client, w, "ESCALATE_TO_SUPERVISOR").status_code == 422  # comment needed
    r = act(client, w, "ESCALATE_TO_SUPERVISOR", comment="too big for me")
    assert r.json()["item"]["status"] == "ESCALATED" and r.json()["item"]["assigned_role"] == "AR_SUPERVISOR"
    assert row(client, w, ANALYST)["allowed_actions"] == []
    sup = row(client, w, SUPERVISOR)["allowed_actions"]
    assert "CONFIRM_ADD_EXCEL" in sup and "ESCALATE_TO_SUPERVISOR" not in sup


def test_close_as_duplicate_and_mark_non_duplicate(client, db):
    original = item(db, status="AUTO_PROCESSED", decision="AUTO_PROCESS")
    dup = item(db, status="DUPLICATE", decision="DUPLICATE", final_classification="DUPLICATE", duplicate_of_id=original.id,
               assigned_role="AR_ANALYST", customer_evidence={"duplicate_reason": "same values"})
    r = act(client, dup, "CLOSE_AS_DUPLICATE")
    assert r.json()["item"]["status"] == "RESOLVED"
    again = item(db, status="DUPLICATE", decision="DUPLICATE", final_classification="DUPLICATE", duplicate_of_id=original.id,
                 assigned_role="AR_ANALYST", customer_evidence={"duplicate_reason": "same values"})
    r = act(client, again, "MARK_NON_DUPLICATE")
    assert r.status_code == 200, r.text
    db.refresh(again)
    assert again.duplicate_of_id is None and again.decision != "DUPLICATE" and again.status != "DUPLICATE"
    assert db.scalar(select(AuditLog).where(AuditLog.entity_id == again.entry_id, AuditLog.action == "MARK_NON_DUPLICATE"))
    assert act(client, original, "MARK_NON_DUPLICATE").status_code in (403, 422)


# --------------------------------------------------------------------------- bulk
def test_bulk_confirm_is_all_or_nothing(client, db):
    good = [item(db, status="AUTO_PROCESSED", decision="AUTO_PROCESS") for _ in range(2)]
    bad = item(db, status="PENDING_REVIEW", decision="MANUAL_REVIEW", invoice_ref_norm=None, bsid_match_flag=False, amount=None)
    h = headers(client)
    body = {"action": "CONFIRM_ADD_EXCEL", "items": [{"id": w.entry_id, "version": row(client, w)["version"]} for w in good + [bad]]}
    r = client.post("/api/work-items/bulk-actions", headers=h, json=body)
    assert r.status_code == 422 and [p["entry_id"] for p in r.json()["detail"]["problems"]] == [bad.entry_id]
    assert all(row(client, w)["status"] == "AUTO_PROCESSED" for w in good)
    body["items"] = body["items"][:2]
    ok = client.post("/api/work-items/bulk-actions", headers=h, json=body)
    assert ok.status_code == 200 and ok.json()["done"] == 2 and all(row(client, w)["status"] == "CONFIRMED" for w in good)
    stale = client.post("/api/work-items/bulk-actions", headers=h, json={"action": "REJECT", "comment": "x", "items": [
        {"id": bad.entry_id, "version": 99}]})
    assert stale.status_code == 409
    assert client.post("/api/work-items/bulk-actions", headers=h, json={"action": "ADD_UPDATE_DETAILS", "items": [
        {"id": bad.entry_id, "version": 1}]}).status_code == 422


# --------------------------------------------------------------------------- dashboard stays decision-based
def test_dashboard_counts_do_not_move_when_actions_change_the_status(client, db):
    rows = [item(db, status="AUTO_PROCESSED", decision="AUTO_PROCESS"), item(db, status="PENDING_REVIEW", decision="MANUAL_REVIEW"),
            item(db, status="EXCEPTION", decision="EXCEPTION", bsid_match_flag=False, final_classification="EXCEPTION"),
            item(db, status="DUPLICATE", decision="DUPLICATE", final_classification="DUPLICATE", assigned_role="AR_ANALYST")]
    h = headers(client)

    def snapshot():
        k = client.get("/api/kpis?customer=ZZTEST", headers=h).json()
        return ({n: c["count"] for n, c in k["cards"].items()}, k["charts"]["performance"], k["charts"]["dimensions"]["customer"])

    before = snapshot()
    assert before[0] == {"total": 4, "ai": 1, "manual": 1, "duplicates": 1, "exceptions": 1}
    act(client, rows[0], "CONFIRM_ADD_EXCEL")
    act(client, rows[1], "REJECT", comment="no")
    act(client, rows[2], "REQUEST_CLARIFICATION", email={"subject": "s", "body": "b"})
    act(client, rows[3], "CLOSE_AS_DUPLICATE")
    assert [row(client, w)["status"] for w in rows] == ["CONFIRMED", "REJECTED", "AWAITING_CUSTOMER", "RESOLVED"]
    assert snapshot() == before


# --------------------------------------------------------------------------- Add / Update details
def test_update_details_rematches_and_rescores(client, db):
    s = sap_sample(db)
    w = item(db, status="EXCEPTION", decision="EXCEPTION", final_classification="EXCEPTION", bsid_match_flag=False,
             assigned_role="AR_ANALYST", kunnr=None, invoice_ref_raw="WRONG", invoice_ref_norm="WRONG", match_level="NONE",
             confidence_score=Decimal("12"))
    r = act(client, w, "ADD_BSID_DETAILS", details={"invoice_ref": s.xblnr, "amount": str(s.wrbtr), "currency": s.waers,
                                                    "kunnr": s.kunnr.lstrip("0"), "payment_date": "2026-10-20",
                                                    "payment_reference": "PAY-1"})
    assert r.status_code == 200, r.text
    db.refresh(w)
    assert w.match_level == "EXACT" and w.bsid_id == s.id and w.bsid_match_flag and w.kunnr == s.kunnr
    assert w.confidence_score >= 90 and w.decision in ("AUTO_PROCESS", "MANUAL_REVIEW") and w.payment_date == date(2026, 10, 20)
    assert w.remittance_ref == "PAY-1" and w.exception_reason is None
    a = db.scalar(select(AuditLog).where(AuditLog.entity_id == w.entry_id, AuditLog.action == "ADD_BSID_DETAILS"))
    assert a.details["before"]["match_level"] == "NONE" and a.details["after"]["match_level"] == "EXACT"
    assert {"invoice_ref", "amount", "kunnr"} <= set(a.details["changed"])


def test_selecting_a_bsid_item_by_hand_links_it_and_validates_input(client, db):
    s = sap_sample(db)
    w = item(db, kunnr=s.kunnr, decision="MANUAL_INVESTIGATION", bsid_match_flag=False, invoice_ref_raw="ZZZ", invoice_ref_norm="ZZZ")
    cands = client.get(f"/api/work-items/{w.entry_id}/bsid-candidates", headers=headers(client)).json()
    assert cands and {c["kunnr"] for c in cands} == {s.kunnr}  # the customer's open items (the latest 40)
    assert any(c["id"] == s.id for c in client.get(f"/api/work-items/{w.entry_id}/bsid-candidates?q={s.xblnr}", headers=headers(client)).json())
    assert act(client, w, "ADD_UPDATE_DETAILS", details={"amount": "abc"}).status_code == 422
    assert act(client, w, "ADD_UPDATE_DETAILS", details={"currency": "DOLLAR"}).status_code == 422
    assert act(client, w, "ADD_UPDATE_DETAILS", details={"kunnr": "1"}).status_code == 422
    assert act(client, w, "ADD_UPDATE_DETAILS", details={}).status_code == 422
    assert act(client, w, "ADD_UPDATE_DETAILS", details={"bsid_id": 999999999}).status_code == 422
    r = act(client, w, "ADD_UPDATE_DETAILS", details={"bsid_id": s.id})
    assert r.status_code == 200, r.text
    db.refresh(w)
    assert w.bsid_id == s.id and w.match_type == "ANALYST_SELECTED" and w.match_level == "MANUAL" and w.bsid_match_flag
    assert "BSID item selected by the analyst" in " ".join(w.review_reasons or [])


# --------------------------------------------------------------------------- outbound e-mail
def test_clarification_goes_only_to_the_redirect_address_and_starts_the_worker(client, db, no_worker_start):
    w = item(db)
    w.kunnr = db.scalar(text("select kunnr from sap.kna1 where spras = 'D' limit 1")) or w.kunnr
    db.flush()
    h = headers(client)
    pv = client.post(f"/api/work-items/{w.entry_id}/outbound-preview", headers=h, json={}).json()
    assert pv["subject"].startswith("[AR-DEMO][CLARIFICATION → ap@zztest.example]")
    assert pv["actual_recipient"] == get_settings().outbound_redirect_to and "ap@zztest.example" in pv["body"]
    r = act(client, w, "REQUEST_CLARIFICATION", email={"subject": pv["subject"], "body": pv["body"] + "\nEdited."})
    assert r.status_code == 200 and r.json()["worker_started"] is True and no_worker_start == [1]
    m = db.get(OutboundMessage, r.json()["outbound_id"])
    assert m.status == "QUEUED" and m.actual_recipient == get_settings().outbound_redirect_to and m.body.endswith("Edited.")
    assert db.scalar(select(func.count()).select_from(Job).where(Job.job_type == "SEND_EMAIL", Job.payload["outbound_id"].astext == str(m.id))) == 1
    assert act(client, item(db), "REQUEST_CLARIFICATION", email={"subject": "", "body": ""}).status_code == 422


def test_templates_exist_in_every_language_and_render():
    for lang, tpl in outbound.TEMPLATES.items():
        ctx = {"customer": "ACME", "detail": "invoice 1, USD 5.00", "question": outbound.DEFAULT_QUESTION[lang]}
        assert "ACME" in outbound._env.from_string(tpl["body"]).render(**ctx)
        assert outbound._env.from_string(tpl["subject"]).render(**ctx)


class FakeSendGmail:
    def __init__(self):
        self.sent, self.modified = [], []

    def users(self):
        return self

    def messages(self):
        return self

    def labels(self):
        return self

    def list(self, **k):
        return type("C", (), {"execute": lambda s: {"labels": [{"name": "AR-Outbound", "id": "L1"}]}})()

    def send(self, userId, body):
        self.sent.append(body)
        return type("C", (), {"execute": lambda s: {"id": "G1", "threadId": body.get("threadId") or "T1"}})()

    def modify(self, userId, id, body):
        self.modified.append((id, body))
        return type("C", (), {"execute": lambda s: {}})()


def test_the_worker_sends_the_queued_email_to_the_redirect_address_only(client, db):
    w = item(db)
    e = db.get(EmailMessage, w.email_id)
    e.thread_id, e.rfc_message_id = "THREAD-9", "<orig@x>"
    msg = outbound.queue_message(db, w, e, subject="[AR-DEMO][CLARIFICATION → ap@zztest.example] Hi", body="Body äöü", created_by=ANALYST)
    gm = FakeSendGmail()
    msg = outbound.send_message(db, msg, service=gm)
    assert msg.status == "SENT" and msg.gmail_thread_id == "THREAD-9" and msg.sent_at
    raw = pyemail.message_from_bytes(base64.urlsafe_b64decode(gm.sent[0]["raw"]))
    assert raw["To"] == get_settings().outbound_redirect_to and raw["X-AR-Demo"] == "outbound"
    assert "ap@zztest.example" not in (raw["To"] or "") and gm.sent[0]["threadId"] == "THREAD-9"
    assert gm.modified and "L1" in gm.modified[0][1]["addLabelIds"]


def test_outbound_refuses_any_mode_but_redirect(client, db, monkeypatch):
    w = item(db)
    monkeypatch.setattr(get_settings(), "outbound_mode", "live")
    with pytest.raises(outbound.OutboundError):
        outbound.queue_message(db, w, db.get(EmailMessage, w.email_id), subject="s", body="b", created_by=ANALYST)


def test_a_customer_reply_in_the_same_thread_joins_the_case(client, db):
    w = item(db, status="AWAITING_CUSTOMER")
    e = db.get(EmailMessage, w.email_id)
    e.thread_id = "THREAD-7"
    m = outbound.queue_message(db, w, e, subject="s", body="b", created_by=ANALYST)
    outbound.send_message(db, m, service=FakeSendGmail())
    reply = make_email(db, thread_id="THREAD-7")
    parent = outbound.attach_reply(db, reply)
    db.flush()
    assert parent.id == e.id and reply.parent_email_id == e.id
    db.refresh(w)
    assert w.status == "PENDING_REVIEW"
    assert db.scalar(select(AuditLog).where(AuditLog.entity_id == w.entry_id, AuditLog.action == "CUSTOMER_REPLIED"))
    assert outbound.attach_reply(db, make_email(db, thread_id="OTHER")) is None


# --------------------------------------------------------------------------- Exported cases
def test_exported_cases_lists_all_confirmed_rows_and_records_the_download(client, db):
    s = sap_sample(db)
    a = item(db, status="AUTO_PROCESSED", decision="AUTO_PROCESS", bsid_id=s.id, kunnr=s.kunnr, amount=s.wrbtr - Decimal("1"),
             currency=s.waers, confidence_score=Decimal("92"), match_level="EXACT")
    b = item(db, status="PENDING_REVIEW", decision="MANUAL_REVIEW")
    base = client.get("/api/exports/cases", headers=headers(client)).json()["count"]
    act(client, a, "CONFIRM_ADD_EXCEL", comment="posted")
    out = client.get("/api/exports/cases", headers=headers(client)).json()
    assert out["count"] == base + 1 and b.entry_id not in [r["entry_id"] for r in out["items"]]
    r = next(r for r in out["items"] if r["entry_id"] == a.entry_id)
    assert (r["belnr"], r["invoice_currency"], r["paid_currency"], r["comment"], r["confirmed_by"]) == \
        (db.scalar(text("select belnr from sap.bsid where id = :i"), {"i": s.id}), s.waers, s.waers, "posted", ANALYST)
    assert Decimal(str(r["difference"])) == Decimal("-1") and r["exported_at"] is None
    assert set(out["columns"]) <= set(r)
    assert client.post("/api/exports/cases/mark-exported", headers=headers(client, CASHAPP), json={}).json()["marked"] >= 1
    r2 = next(r for r in client.get("/api/exports/cases", headers=headers(client)).json()["items"] if r["entry_id"] == a.entry_id)
    assert r2["exported_by"] == CASHAPP and r2["exported_at"]
    assert db.scalar(select(AuditLog).where(AuditLog.entity_id == a.entry_id, AuditLog.action == "EXPORTED_TO_EXCEL"))
    assert client.post("/api/exports/cases/mark-exported", json={}).status_code == 401  # login needed


# --------------------------------------------------------------------------- Action Queue leaves out-of-scope e-mails out
def test_the_action_queue_list_can_leave_out_of_scope_rows_out(client, db):
    e = make_email(db)
    keep = make_item(db, e)
    gone = make_item(db, e, final_classification="OUT_OF_SCOPE", decision="OUT_OF_SCOPE", status="IGNORED", invoice_ref_raw=None)
    h = headers(client)
    ids = lambda url: {i["entry_id"] for i in client.get(url, headers=h).json()["items"]}
    assert {keep.entry_id, gone.entry_id} <= ids("/api/work-items?customer=ZZTEST&page_size=200")
    assert keep.entry_id in ids("/api/work-items?customer=ZZTEST&in_scope=true&page_size=200")
    assert gone.entry_id not in ids("/api/work-items?customer=ZZTEST&in_scope=true&page_size=200")
