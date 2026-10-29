"""M07: demo login, workbench endpoints, KPIs with USD conversion, signed file links, change feed, performance."""
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app import fx
from app.api import auth
from app.config import get_settings
from app.db import get_db
from app.main import app
from app.models.ar import AuditLog, EmailAttachment, EmailMessage, WorkItem
from app.permissions import allowed_actions
from app.storage import LocalStorage

CODE = "demo-code-for-tests"
USER = "analyst@acme-demo.local"


@pytest.fixture(autouse=True)
def login_on(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "demo_access_code", CODE)
    monkeypatch.setattr(s, "jwt_secret", "k" * 40)
    auth.limiter.reset()
    yield
    auth.limiter.reset()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


def login(client, user=USER, code=CODE):
    return client.post("/api/auth/demo-login", json={"user": user, "access_code": code})


def headers(client, user=USER):
    return {"Authorization": f"Bearer {login(client, user).json()['token']}"}


def make_email(db, **kw) -> EmailMessage:
    ref = f"EML-T{uuid.uuid4().hex[:8]}"
    e = EmailMessage(email_ref=ref, source="sample", sender_email="ap@zztest.example", sender_domain="zztest.example",
                     subject="Remittance", received_at=kw.pop("received_at", datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)),
                     status="PROCESSED", body_text="body", body_text_clean="body", **kw)
    db.add(e)
    db.flush()
    return e


def make_item(db, e, **kw) -> WorkItem:
    defaults = dict(entry_id=f"TST-{uuid.uuid4().hex[:10].upper()}", email_id=e.id, final_classification="REMITTANCE",
                    customer_name="ZZTEST Corp", kunnr="0000999999", bukrs="1000", status="PENDING_REVIEW",
                    decision="MANUAL_REVIEW", assigned_role="CASH_APPLICATION", bsid_match_flag=True)
    w = WorkItem(**{**defaults, **kw})
    db.add(w)
    db.flush()
    return w


# --------------------------------------------------------------------------- login
def test_login_gives_a_token_and_wrong_credentials_get_the_same_401(client, db):
    ok = login(client)
    assert ok.status_code == 200 and ok.json()["user"]["role"] == "AR_ANALYST" and ok.json()["token_type"] == "Bearer"
    wrong_code, no_user = login(client, code="nope"), login(client, user="nobody@x.y")
    assert wrong_code.status_code == no_user.status_code == 401 and wrong_code.json() == no_user.json()
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {ok.json()['token']}"}).json()["email"] == USER
    assert len(client.get("/api/auth/demo-users").json()) == 4


def test_login_is_off_without_configuration(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_access_code", "")
    assert login(client).status_code == 503


def test_data_endpoints_need_a_token(client):
    for url in ("/api/work-items", "/api/work-items/1", "/api/kpis", "/api/audit", "/api/changes?since=2026-01-01T00:00:00Z"):
        assert client.get(url).status_code == 401, url
    assert client.get("/api/work-items", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_expired_token_is_401_and_lifetime_is_hours(client, monkeypatch):
    claims = jwt.decode(login(client).json()["token"], options={"verify_signature": False})
    assert 8 * 3600 <= claims["exp"] - claims["iat"] <= 12 * 3600
    monkeypatch.setattr(get_settings(), "token_hours", -1)
    r = client.get("/api/work-items", headers={"Authorization": f"Bearer {login(client).json()['token']}"})
    assert r.status_code == 401 and "expired" in r.json()["detail"].lower()


def test_login_is_rate_limited_then_locked_out_then_free_again(client, db, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(auth, "limiter", auth.LoginLimiter(clock=lambda: now[0]))
    codes = [login(client, code="wrong").status_code for _ in range(10)]
    assert codes == [401] * 10
    blocked = login(client, code="wrong")
    assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) > 0
    assert login(client).status_code == 429  # even the right code is refused during the lockout
    now[0] += get_settings().login_lockout_s + 1
    assert login(client).status_code == 200
    assert len(db.scalars(select(AuditLog).where(AuditLog.action == "LOGIN_BLOCKED")).all()) == 1  # logged once


def test_logins_are_audited_and_the_code_is_never_logged(client, db):
    login(client, code="secret-guess-777")
    login(client)
    rows = db.scalars(select(AuditLog).where(AuditLog.entity_type == "auth").order_by(AuditLog.id.desc()).limit(2)).all()
    assert {r.action for r in rows} == {"LOGIN_OK", "LOGIN_FAILED"}
    dump = " ".join(str(r.details) + (r.actor or "") for r in db.scalars(select(AuditLog).where(AuditLog.entity_type == "auth")))
    assert "secret-guess-777" not in dump and CODE not in dump


# --------------------------------------------------------------------------- USD conversion
def test_fx_uses_latest_rate_on_or_before_and_flags_missing_rates():
    t = fx.RateTable({"EUR": [(date(2026, 1, 1), Decimal("1.10")), (date(2026, 6, 1), Decimal("1.20"))],
                      "JPY": [(date(2026, 1, 1), Decimal("0.0070"))], "KWD": [(date(2026, 1, 1), Decimal("3.25"))]},
                     {"JPY": 0, "KWD": 3})
    assert t.to_usd(Decimal("100"), "EUR", date(2026, 5, 31)) == (Decimal("110.00"), "OK")
    assert t.to_usd(Decimal("100"), "EUR", date(2026, 6, 1)) == (Decimal("120.00"), "OK")  # on the day
    assert t.to_usd(Decimal("100"), "EUR", date(2025, 12, 31)) == (None, "NO_RATE")      # before the first rate
    assert t.to_usd(Decimal("100"), "ABC", date(2026, 6, 1)) == (None, "NO_RATE")
    assert t.to_usd(Decimal("12345.6"), "JPY", date(2026, 2, 1)) == (Decimal("86.42"), "OK")  # rounded to 12346 first
    assert t.to_usd(Decimal("1.2345"), "KWD", date(2026, 2, 1)) == (Decimal("4.01"), "OK")    # 3 decimals kept: 1.235 x 3.25
    assert t.to_usd(Decimal("50.5"), "USD", None) == (Decimal("50.50"), "OK")
    assert t.to_usd(None, "EUR", date(2026, 2, 1)) == (None, "NO_AMOUNT")


def test_fx_loads_the_real_tables_with_the_per_100_factor(db):
    t = fx.load_rates(db)
    assert t.decimals["JPY"] == 0 and t.decimals["KWD"] == 3
    row = db.execute(text("select ukurs, ffact, tfact, gdatu from sap.tcurr where fcurr='JPY' and tcurr='USD' and kurst='M' "
                          "order by gdatu desc limit 1")).one()
    assert t.rate("JPY", row.gdatu) == Decimal(row.ukurs) * Decimal(row.tfact) / Decimal(row.ffact)


# --------------------------------------------------------------------------- permissions
def test_allowed_actions_follow_the_knowledge_base_table():
    assert allowed_actions("AR_ANALYST", "EXCEPTION", "EXCEPTION", "AR_ANALYST") == [
        "ADD_BSID_DETAILS", "CONFIRM_EXTRACT_EXCEL", "REQUEST_CLARIFICATION", "REJECT"]
    assert "ESCALATE_TO_SUPERVISOR" in allowed_actions("CASH_APPLICATION", "MANUAL_INVESTIGATION", "PENDING_REVIEW", "CASH_APPLICATION")
    assert "ESCALATE_TO_SUPERVISOR" not in allowed_actions("AR_SUPERVISOR", "MANUAL_INVESTIGATION", "PENDING_REVIEW", "CASH_APPLICATION")
    assert allowed_actions("AR_ANALYST", "DUPLICATE", "DUPLICATE", "AR_ANALYST") == [
        "CLOSE_AS_DUPLICATE", "REQUEST_CLARIFICATION", "MARK_NON_DUPLICATE", "ADD_UPDATE_DETAILS"]
    assert allowed_actions("COLLECTIONS_ANALYST", "MANUAL_REVIEW", "PENDING_REVIEW", "CASH_APPLICATION") == []  # not theirs
    assert allowed_actions("AR_SUPERVISOR", "MANUAL_REVIEW", "RESOLVED", "CASH_APPLICATION") == []            # closed
    assert allowed_actions("AR_ANALYST", "AUTO_PROCESS", "CONFIRMED", "CASH_APPLICATION") == []               # already confirmed
    assert allowed_actions("AR_SUPERVISOR", "OUT_OF_SCOPE", "IGNORED", None) == []


def test_every_row_carries_the_actions_of_the_current_user(client, db):
    e = make_email(db)
    make_item(db, e)
    for user, expect in (("cashapp@acme-demo.local", True), ("collections@acme-demo.local", False)):
        items = client.get("/api/work-items?customer=ZZTEST", headers=headers(client, user)).json()["items"]
        assert bool(items[0]["allowed_actions"]) is expect


# --------------------------------------------------------------------------- list, filters, detail
def test_list_filters_sorting_and_paging(client, db):
    e1, e2 = make_email(db), make_email(db, received_at=datetime(2026, 9, 1, tzinfo=timezone.utc))
    a = make_item(db, e1, amount=Decimal("100"), currency="USD", confidence_score=Decimal("95"), region="EMEA", invoice_ref_raw="INV-ZZ-1")
    b = make_item(db, e1, amount=Decimal("300"), currency="USD", confidence_score=Decimal("50"), bukrs="2000",
                  bsid_match_flag=False, status="EXCEPTION", decision="EXCEPTION")
    c = make_item(db, e2, amount=Decimal("200"), currency="USD", confidence_score=Decimal("10"), final_classification="PTP")
    h = headers(client)
    get = lambda qs: client.get(f"/api/work-items?customer=ZZTEST&{qs}", headers=h).json()
    assert get("")["total"] == 3
    assert {i["id"] for i in get("status=EXCEPTION")["items"]} == {b.id}
    assert {i["id"] for i in get("bsid_match=false")["items"]} == {b.id}
    assert {i["id"] for i in get("company_code=2000")["items"]} == {b.id}
    assert {i["id"] for i in get("region=EMEA")["items"]} == {a.id}
    assert {i["id"] for i in get("classification=PTP")["items"]} == {c.id}
    assert {i["id"] for i in get("min_confidence=40&max_confidence=99")["items"]} == {a.id, b.id}
    assert {i["id"] for i in get("from_date=2026-10-01")["items"]} == {a.id, b.id}
    assert {i["id"] for i in get("to_date=2026-09-30")["items"]} == {c.id}
    assert {i["id"] for i in get("q=INV-ZZ-1")["items"]} == {a.id}
    assert [i["id"] for i in get("sort=amount&order=asc")["items"]] == [a.id, c.id, b.id]
    p = get("sort=amount&order=desc&page=2&page_size=2")
    assert p["total"] == 3 and [i["id"] for i in p["items"]] == [a.id]
    assert client.get("/api/work-items?sort=password", headers=h).status_code == 422


def test_detail_has_email_attachments_signed_links_evidence_candidates_and_audit(client, db, tmp_path, monkeypatch):
    storage = LocalStorage(tmp_path / "f")
    monkeypatch.setattr("app.api.workitems.get_storage", lambda: storage)
    e = make_email(db)
    w = make_item(db, e, extraction_evidence={"amount": {"page": 1}})
    uri = storage.put("x/remittance.pdf", b"%PDF-1.4 test", "application/pdf")
    att = EmailAttachment(email_id=e.id, filename="remittance.pdf", mime_type="application/pdf", size_bytes=13,
                          sha256="a" * 64, storage_uri=uri, depth=0, text_content="text", layout={"pages": []})
    db.add(att)
    db.add(AuditLog(actor="system", entity_type="work_item", entity_id=w.entry_id, action="TEST_EVENT"))
    db.flush()
    resp = client.get(f"/api/work-items/{w.entry_id}", headers=headers(client))
    assert resp.status_code == 200, resp.text[:400]
    d = resp.json()
    assert d["entry_id"] == w.entry_id and d["email"]["email_ref"] == e.email_ref and d["evidence"] == {"amount": {"page": 1}}
    assert "raw_uri" not in d["email"] and "storage_uri" not in d["attachments"][0] and "layout" not in d["attachments"][0]
    assert any(a["action"] == "TEST_EVENT" for a in d["audit"])
    assert {"allowed_actions", "candidates", "score_breakdown", "same_email_items"} <= set(d)
    # the signed link works without any header, and only for this attachment
    url = d["attachments"][0]["url"]
    f = client.get(url)
    assert f.status_code == 200 and f.content == b"%PDF-1.4 test" and f.headers["content-type"] == "application/pdf"
    assert f.headers["content-disposition"].startswith("inline") and f.headers["x-content-type-options"] == "nosniff"
    assert client.get(url.replace(f"/{att.id}/", f"/{att.id + 1}/")).status_code in (401, 404)
    assert client.get("/api/work-items/ENT-NOPE", headers=headers(client)).status_code == 404
    lay = client.get(f"/api/attachments/{att.id}/layout", headers=headers(client)).json()
    assert lay["layout"] == {"pages": []} and client.get(f"/api/attachments/{att.id}/layout").status_code == 401


def test_file_links_expire_and_html_is_never_shown_inline(client, db, tmp_path, monkeypatch):
    storage = LocalStorage(tmp_path / "f")
    monkeypatch.setattr("app.api.workitems.get_storage", lambda: storage)
    e = make_email(db)
    att = EmailAttachment(email_id=e.id, filename="evil.html", mime_type="text/html", size_bytes=5, sha256="b" * 64,
                          storage_uri=storage.put("x/evil.html", b"<script>", "text/html"), depth=0)
    db.add(att)
    db.flush()
    f = client.get(f"/api/attachments/{att.id}/file?token={auth.make_file_token(att.id, USER)}")
    assert f.headers["content-disposition"].startswith("attachment") and f.headers["content-type"] == "application/octet-stream"
    monkeypatch.setattr(get_settings(), "file_url_ttl_s", -5)
    old = client.get(f"/api/attachments/{att.id}/file?token={auth.make_file_token(att.id, USER)}")
    assert old.status_code == 401 and "expired" in old.json()["detail"].lower()
    assert client.get(f"/api/attachments/{att.id}/file?token={login(client).json()['token']}").status_code == 401  # access token is no file link
    assert get_settings().file_url_ttl_s == -5  # (restored by monkeypatch)


# --------------------------------------------------------------------------- KPIs
def _expected_usd(db, amount: str, cur: str, on: date) -> Decimal:
    r = db.execute(text("select ukurs, ffact, tfact from sap.tcurr where fcurr=:c and tcurr='USD' and kurst='M' and gdatu <= :d "
                        "order by gdatu desc limit 1"), {"c": cur, "d": on}).one()
    dec = db.execute(text("select currdec from sap.tcurx where currkey=:c"), {"c": cur}).scalar() or 2
    a = Decimal(amount).quantize(Decimal(1).scaleb(-dec))
    return (a * Decimal(r.ukurs) * Decimal(r.tfact) / Decimal(r.ffact)).quantize(Decimal("0.01"))


def test_kpis_sum_usd_per_card_and_flag_rows_without_a_rate(client, db):
    e = make_email(db)
    d = date(2026, 10, 12)
    make_item(db, e, status="AUTO_PROCESSED", decision="AUTO_PROCESS", amount=Decimal("100"), currency="EUR", payment_date=d)
    make_item(db, e, status="AUTO_PROCESSED", decision="AUTO_PROCESS", amount=Decimal("10000"), currency="JPY", payment_date=d)
    make_item(db, e, status="AUTO_PROCESSED", decision="AUTO_PROCESS", amount=Decimal("50.5"), currency="USD", payment_date=d)
    make_item(db, e, status="PENDING_REVIEW", amount=Decimal("77"), currency="XXX", payment_date=d)   # no rate
    make_item(db, e, status="DUPLICATE", decision="DUPLICATE", amount=Decimal("1.234"), currency="KWD", payment_date=d)
    make_item(db, e, status="EXCEPTION", decision="EXCEPTION", amount=Decimal("5"), currency="GBP", payment_date=date(2000, 1, 1))  # before first rate
    k = client.get("/api/kpis?customer=ZZTEST", headers=headers(client)).json()
    c = k["cards"]
    assert [c[x]["count"] for x in ("total", "ai", "manual", "duplicates", "exceptions")] == [6, 3, 1, 1, 1]
    ai = _expected_usd(db, "100", "EUR", d) + _expected_usd(db, "10000", "JPY", d) + Decimal("50.50")
    assert Decimal(str(c["ai"]["usd"])) == ai
    assert Decimal(str(c["duplicates"]["usd"])) == _expected_usd(db, "1.234", "KWD", d)
    assert c["manual"]["usd"] == 0 and c["exceptions"]["usd"] == 0       # unconverted rows are left out of the sums...
    assert k["usd"]["unconverted"] == 2 and k["usd"]["missing_rate_currencies"] == {"XXX": 1, "GBP": 1}  # ...and flagged
    assert k["distributions"]["customer"][0]["label"] == "ZZTEST Corp" and k["distributions"]["customer"][0]["count"] == 6
    assert k["monthly_trend"][-1]["month"] in ("2026-10", "2000-01")
    day = next(x for x in k["performance_stability"] if x["date"] == "2026-10-12")
    assert day["rows"] == 5 and day["auto_rate"] == 0.6


def test_kpis_follow_the_filters(client, db):
    e = make_email(db)
    make_item(db, e, status="AUTO_PROCESSED", decision="AUTO_PROCESS", amount=Decimal("1"), currency="USD", region="APAC")
    make_item(db, e, status="PENDING_REVIEW", amount=Decimal("2"), currency="USD", region="EMEA")
    k = client.get("/api/kpis?customer=ZZTEST&region=APAC", headers=headers(client)).json()
    assert k["cards"]["total"]["count"] == 1 and k["cards"]["ai"]["count"] == 1


# --------------------------------------------------------------------------- change feed, audit list, CORS
def test_changes_feed_reports_new_and_updated_rows_only(client, db):
    h = headers(client)
    start = client.get("/api/changes?since=2100-01-01T00:00:00Z", headers=h).json()
    assert start["changed"] is False and start["new_work_items"]["count"] == 0
    since = start["next_since"]   # the server time minus 60 s, so rows of a slow transaction are not missed
    e = make_email(db)
    w = make_item(db, e)
    r = client.get("/api/changes", params={"since": since}, headers=h).json()
    assert w.id in r["new_work_items"]["ids"] and r["new_emails"] >= 1 and r["changed"] is True
    later = r["server_time"]
    assert client.get("/api/changes", params={"since": later}, headers=h).json()["new_work_items"]["count"] == 0


def test_audit_list_filters(client, db):
    db.add(AuditLog(actor="zz.tester", entity_type="work_item", entity_id="TST-AUD", action="TEST_AUDIT"))
    db.flush()
    r = client.get("/api/audit?actor=zz.tester&action=test_audit", headers=headers(client)).json()
    assert r["total"] == 1 and r["items"][0]["entity_id"] == "TST-AUD"


def test_cors_allows_only_the_configured_origins(client):
    ok = client.options("/api/work-items", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    bad = client.options("/api/work-items", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in bad.headers
    assert "*" not in get_settings().cors_origins


# --------------------------------------------------------------------------- performance (history-size set)
def test_responses_stay_under_one_second_on_a_history_sized_set(client, db):
    e = make_email(db)
    base = datetime(2026, 7, 28, tzinfo=timezone.utc)
    emails = [make_email(db, received_at=base + timedelta(hours=7 * i)) for i in range(250)]
    db.execute(WorkItem.__table__.insert(), [dict(
        entry_id=f"PERF-{uuid.uuid4().hex[:10]}", email_id=emails[i % 250].id, line_no=1, final_classification="REMITTANCE",
        customer_name=f"ZZPERF Customer {i % 60}", kunnr=f"{i % 60:010d}", bukrs=("1000", "2000", "3000")[i % 3],
        region=("EMEA", "APAC", "AMER")[i % 3], amount=Decimal(100 + i), currency=("USD", "EUR", "JPY", "GBP", "INR")[i % 5],
        status=("AUTO_PROCESSED", "PENDING_REVIEW", "EXCEPTION", "DUPLICATE")[i % 4], decision="MANUAL_REVIEW",
        confidence_score=Decimal(i % 100), bsid_match_flag=True) for i in range(5000)])
    h = headers(client)
    for url in ("/api/work-items?customer=ZZPERF&page_size=50", "/api/work-items?customer=ZZPERF&sort=amount&q=PERF",
                "/api/kpis?customer=ZZPERF", "/api/kpis?customer=ZZPERF&region=EMEA", "/api/audit?page_size=50"):
        t = time.perf_counter()
        r = client.get(url, headers=h)
        assert r.status_code == 200 and time.perf_counter() - t < 1.0, url
    assert client.get("/api/kpis?customer=ZZPERF", headers=h).json()["cards"]["total"]["count"] == 5000


def test_pdf_pages_are_served_as_images_for_the_viewer(client, db, tmp_path, monkeypatch):
    import pymupdf

    doc = pymupdf.open()
    doc.new_page(width=300, height=200).insert_text((20, 40), "Remittance advice")
    pdf = doc.tobytes()
    storage = LocalStorage(tmp_path / "f")
    monkeypatch.setattr("app.api.workitems.get_storage", lambda: storage)
    e = make_email(db)
    w = make_item(db, e)
    att = EmailAttachment(email_id=e.id, filename="a.pdf", mime_type="application/pdf", size_bytes=len(pdf), sha256="c" * 64,
                          storage_uri=storage.put("x/a.pdf", pdf, "application/pdf"), depth=0, page_count=1)
    db.add(att)
    db.flush()
    d = client.get(f"/api/work-items/{w.entry_id}", headers=headers(client)).json()
    template = d["attachments"][0]["page_url"]
    assert "{page}" in template
    img = client.get(template.replace("{page}", "1"))
    assert img.status_code == 200 and img.headers["content-type"] == "image/png" and img.content[:4] == b"\x89PNG"
    assert client.get(template.replace("{page}", "2")).status_code == 404
    assert client.get(f"/api/attachments/{att.id}/page/1").status_code == 422  # no token
