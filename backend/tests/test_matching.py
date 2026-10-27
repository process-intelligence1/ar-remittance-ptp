"""M05: invoice matching (EXACT / NEAR / NONE), scoring incl. confidence = max(fast path, formula) and the
KB worked example, customer identification, amount combinations, duplicates, decisions, saving, API."""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.classification.service import classify_email
from app.config import get_settings
from app.db import get_db
from app.documents.service import parse_email
from app.extraction.refs import normalise_ref
from app.extraction.service import extract_email
from app.gmail.poller import store_email
from app.gmail.sample_sender import build_message, load_sample
from app.main import app
from app.matching.customers import identify, name_similarity
from app.matching.data import Customer, OpenItem, SapData
from app.matching.duplicates import RowKey, find_original
from app.matching.invoice_match import compare, find_matches
from app.matching.matcher import LineIn, MatchInput, match_email
from app.matching.scoring import score
from app.matching.service import AlreadyWorkedOn, NotExtractedYet, match_stored_email
from app.matching.unreferenced import find_combinations
from app.models.ar import MatchCandidate, PtpCommitment, WorkItem
from app.rules_defaults import DEFAULT_RULES

RULES = {k: v[0] for k, v in DEFAULT_RULES.items()}
IM = RULES["invoice_match"]
BD = date(2026, 10, 28)


# --------------------------------------------------------------------------- a small SAP world
def item(id, xblnr, amount, *, kunnr="0000100001", bukrs="1000", cur="USD", belnr=None, vbeln=None, shkzg="S",
         bldat=date(2026, 9, 1), blocked=False):
    a = D(str(amount))
    return OpenItem(id, bukrs, kunnr, belnr or f"90000{id:05d}", xblnr, vbeln, cur, -a if shkzg == "H" else a, shkzg,
                    bldat, bldat, blocked)


def world(items, *, customers=None, addresses=None, ibans=None, paid_by=None):
    by = {"x": defaultdict(list), "b": defaultdict(list), "v": defaultdict(list), "k": defaultdict(list)}
    for it in items:
        by["k"][it.kunnr].append(it)
        for v, key in ((it.xblnr, "x"), (it.belnr, "b"), (it.vbeln, "v")):
            if normalise_ref(v):
                by[key][normalise_ref(v)].append(it)
    customers = customers or {"0000100001": Customer("0000100001", "Summit Office Solutions Inc.", "US", {"1000"})}
    addresses = addresses or {}
    domains = defaultdict(set)
    for a, ks in addresses.items():
        domains[a.split("@")[1]] |= ks
    return SapData({i.id: i for i in items}, by["x"], by["b"], by["v"], by["k"], customers, addresses, dict(domains),
                   ibans or {}, paid_by or {})


# --------------------------------------------------------------------------- invoice-number levels
@pytest.mark.parametrize("extracted, bsid, level", [
    ("90031280", "90031280", "EXACT"),
    (normalise_ref("0090-031.280"), normalise_ref("90031280"), "EXACT"),       # normalised EXACT
    (normalise_ref("mum / 2627 / 04212"), normalise_ref("MUM/2627/04212"), "EXACT"),
    ("9OO31280", "90031280", "NONE"),       # two characters differ
    ("90O31280", "90031280", "NEAR"),       # 0/O
    ("SI12600517", "S112600517", "NEAR"),   # 1/I
    ("UK1O43617", "UK1043617", "NEAR"),
    ("SI1260O517", "SI12600517", "NEAR"),
    ("9003128B", "90031288", "NEAR"),       # 8/B
    ("SRV1OO354", "SRV100354", "NONE"),     # two differences
    ("90031S80", "90031580", "NEAR"),       # 5/S
    ("JP26OO2Z71", "JP26002271", "NONE"),
    ("JP2600Z271", "JP26002271", "NEAR"),   # 2/Z
    ("SL12600517", "SI12600517", "NEAR"),   # I/L
    ("90031281", "90031280", "NONE"),       # 1 vs 0 is not an OCR pair
    ("9003128", "90031280", "NONE"),        # length differs
    ("23756669", "23756668", "NONE"),       # the KB worked example: 9 vs 8 is not an OCR pair
])
def test_invoice_match_levels(extracted, bsid, level):
    assert compare(extracted, bsid, IM)[0] == level


def test_belnr_and_vbeln_only_exact_xblnr_also_near():
    w = world([item(1, "90031280", 100, belnr="1800012345", vbeln="0090099999")])
    assert [(m.field, m.level) for m in find_matches("1800012345", w, IM)] == [("BELNR", "EXACT")]
    assert [(m.field, m.level) for m in find_matches("90099999", w, IM)] == [("VBELN", "EXACT")]  # leading zeros
    assert find_matches("18000I2345", w, IM) == []                  # NEAR is not accepted on BELNR
    [near] = find_matches("9003128O", w, IM)
    assert (near.field, near.level, near.score, near.detail) == ("XBLNR", "NEAR", 0.70, "0 read as O")


# --------------------------------------------------------------------------- scoring: KB worked example + fast paths
KB = dict(amount=D("13497.36"), currency="USD", bsid_amount=D("13464.77"), bsid_currency="USD", sender_company=True,
          name_similarity=0.957, date_days=144)


def test_worked_example_exact_formula_beats_fast_path():
    s = score(RULES, level="EXACT", invoice_score=1.0, **KB)
    assert s.fast_path == "EXACT_FULL_MATCH" and s.formula_confidence == D("95.32")
    assert (s.confidence, s.confidence_source, s.decision) == (D("95.32"), "FORMULA", "AUTO_PROCESS")


def test_worked_example_near_and_none_unchanged():
    near = score(RULES, level="NEAR", invoice_score=0.70, review_reasons=["Possible OCR misread"], **KB)
    assert (near.confidence, near.confidence_source, near.decision) == (D("83.65"), "FORMULA", "MANUAL_REVIEW")
    none = score(RULES, level="NONE", invoice_score=0.0, **KB)
    assert (none.confidence, none.decision, none.exception_reason) == (D("56.43"), "EXCEPTION", "No BSID match found")
    assert none.raw == D("0.5079") and near.raw == D("0.7529")


def test_exact_amount_missing_fast_path_wins():
    s = score(RULES, level="EXACT", invoice_score=1.0, amount=None, currency="USD", bsid_amount=D("100"),
              bsid_currency="USD", sender_company=True, name_similarity=0.957, date_days=144)
    assert s.formula_confidence < 91 and (s.confidence, s.confidence_source, s.fast_path) == (
        D("91.00"), "FAST_PATH", "EXACT_AMOUNT_MISSING")
    assert s.decision == "AUTO_PROCESS"


def test_fast_path_lifts_a_lower_formula_to_92():
    s = score(RULES, level="EXACT", invoice_score=1.0, amount=D("100"), currency="USD", bsid_amount=D("101"),
              bsid_currency="USD", sender_company=False, name_similarity=0.2, date_days=400)
    assert s.formula_confidence < 92 and (s.confidence, s.confidence_source, s.decision) == (D("92.00"), "FAST_PATH",
                                                                                             "AUTO_PROCESS")


def test_fast_path_values_come_from_rule_config():
    rules = {**RULES, "fast_path": {**RULES["fast_path"], "exact_amount_missing_score": 93}}
    s = score(rules, level="EXACT", invoice_score=1.0, amount=None, currency=None, bsid_amount=D("1"),
              bsid_currency="USD", sender_company=False, name_similarity=0, date_days=None)
    assert s.confidence == D("93.00")


@pytest.mark.parametrize("paid, expected", [(100, 1.0), (97, 0.8), (93, 0.6), (85, 0.3), (70, 0.0)])
def test_amount_bands(paid, expected):
    s = score(RULES, level="NEAR", invoice_score=0.7, amount=D(str(paid)), currency="USD", bsid_amount=D("100"),
              bsid_currency="USD", sender_company=False, name_similarity=0, date_days=0)
    assert s.amount_alignment == expected


def test_currency_mismatch_scores_zero_and_blocks_fast_path():
    s = score(RULES, level="EXACT", invoice_score=1.0, amount=D("100"), currency="EUR", bsid_amount=D("100"),
              bsid_currency="USD", sender_company=True, name_similarity=1, date_days=10)
    assert s.amount_alignment == 0 and s.fast_path is None and s.decision == "MANUAL_REVIEW"


@pytest.mark.parametrize("days, expected", [(10, 1.0), (90, 1.0), (91, 0.6), (180, 0.6), (181, 0.2)])
def test_date_bands(days, expected):
    assert score(RULES, level="NONE", invoice_score=0, amount=None, currency=None, bsid_amount=None, bsid_currency=None,
                 sender_company=False, name_similarity=0, date_days=days).date_proxy == expected


def test_decision_thresholds_and_review_reasons():
    common = dict(currency="USD", bsid_amount=D("100"), bsid_currency="USD", name_similarity=0)
    medium = score(RULES, level="NEAR", invoice_score=0.7, amount=D("100"), sender_company=False, date_days=999, **common)
    low = score(RULES, level="NEAR", invoice_score=0.7, amount=D("10"), sender_company=False, date_days=999, **common)
    assert (medium.category, medium.decision) == ("MEDIUM", "MANUAL_REVIEW")
    assert (low.category, low.decision) == ("LOW", "MANUAL_INVESTIGATION")
    blocked = score(RULES, level="EXACT", invoice_score=1.0, amount=D("100"), sender_company=True, date_days=1,
                    review_reasons=["Payment block on the open item (ZLSPR = R)"], **common)
    assert blocked.category == "HIGH" and blocked.decision == "MANUAL_REVIEW" and blocked.status == "PENDING_REVIEW"


# --------------------------------------------------------------------------- customers
def test_name_similarity_ignores_legal_forms_and_order():
    assert name_similarity("Summit Office Solutions", "Summit Office Solutions Inc.") == 1.0
    assert name_similarity("Weber Buerotechnik GmbH", "WEBER BUEROTECHNIK") == 1.0
    assert name_similarity("Acme", "Totally Different Ltd") < 0.5


def test_identification_order_and_signals():
    custs = {k: Customer(k, n, "US", {"1000"}) for k, n in (("0000100001", "Summit Office Solutions Inc."),
                                                          ("0000100002", "Blue Ridge Hardware LLC"))}
    w = world([item(1, "90031280", 100, kunnr="0000100002")], customers=custs,
              addresses={"ap@summit.com": {"0000100001"}}, ibans={"GB82WEST12345698765432": {"0000100001"}},
              paid_by={"0000100001": {"0000100002"}})
    def who(**kw):
        base = dict(sender_email=None, customer_number=None, iban=None, payer_name=None, exact_invoice_customers=[],
                    name_min=0.85)
        r = identify(w, **(base | kw))
        return r.kunnr, r.method
    assert who(exact_invoice_customers=["0000100002"], sender_email="ap@summit.com") == ("0000100002", "INVOICE")
    assert who(sender_email="AP@Summit.com") == ("0000100001", "SENDER_ADDRESS")
    assert who(customer_number="100002") == ("0000100002", "CUSTOMER_NUMBER")
    assert who(iban="GB82 WEST 1234 5698 7654 32") == ("0000100001", "IBAN")
    assert who(sender_email="treasury@summit.com") == ("0000100001", "SENDER_DOMAIN")
    assert who(payer_name="Blue Ridge Hardware") == ("0000100002", "NAME")
    assert who(sender_email="someone@gmail.com") == (None, None)
    r = identify(w, sender_email="ap@summit.com", customer_number=None, iban=None, payer_name=None,
                 exact_invoice_customers=[], name_min=0.85)
    assert r.allowed == {"0000100001", "0000100002"}  # KNVP: Summit pays for Blue Ridge


# --------------------------------------------------------------------------- matcher
def inp(lines, **kw):
    base = dict(email_key=1, label="REMITTANCE", out_of_scope_category=None, contains_remittance=True,
                sender_email="ap@summit.com", sender_name=None, received_at=None, email_date=BD, business_date=BD,
                attachments=1, lines=lines, payer_name="Summit Office Solutions", payment_currency="USD")
    return MatchInput(**(base | kw))


def test_payment_block_and_credit_note():
    w = world([item(1, "90031280", 6400, blocked=True), item(2, "CN-1031273", 400, shkzg="H")],
              addresses={"ap@summit.com": {"0000100001"}})
    rows = match_email(inp([LineIn("90031280", "90031280", "REMITTANCE", D("6400"), payment_currency="USD"),
                            LineIn("CN-1031273", "CN1031273", "REMITTANCE", D("-400"), credit_note=True,
                                   payment_currency="USD")]), w, RULES)
    blocked, credit = rows
    assert blocked.score.decision == "MANUAL_REVIEW" and "Payment block" in blocked.score.review_reasons[0]
    assert credit.item.amount == D("-400") and credit.score.amount_alignment == 1.0 and credit.score.decision == "AUTO_PROCESS"


def test_third_party_payment_goes_to_review_unless_related_in_knvp():
    custs = {k: Customer(k, n, "SE", {"2000"}) for k, n in (("0000100001", "Lindqvist Industri AB"),
                                                          ("0000100002", "Techniques Avancees du Nord SAS"),
                                                          ("0000100003", "Lindqvist Daughter AB"))}
    items = [item(1, "91005417", 2353.03, kunnr="0000100002", bukrs="2000", cur="EUR"),
             item(2, "91005418", 100, kunnr="0000100003", bukrs="2000", cur="EUR")]
    w = world(items, customers=custs, addresses={"ap@lindqvist.se": {"0000100001"}}, paid_by={"0000100001": {"0000100003"}})
    rows = match_email(inp([LineIn("91005417", "91005417", "REMITTANCE", D("2353.03"), payment_currency="EUR"),
                            LineIn("91005418", "91005418", "REMITTANCE", D("100"), payment_currency="EUR")],
                           sender_email="ap@lindqvist.se", payer_name="Lindqvist Industri", payment_currency="EUR"), w, RULES)
    other, daughter = rows
    assert other.kunnr == "0000100002" and other.score.decision == "MANUAL_REVIEW"
    assert "but the e-mail comes from customer 100001" in other.score.review_reasons[0]
    assert not any("comes from" in r for r in daughter.score.review_reasons)  # Lindqvist pays for its daughter (RG)


def test_unknown_invoice_is_an_exception_and_out_of_scope_is_ignored():
    w = world([item(1, "90031280", 100)], addresses={"ap@summit.com": {"0000100001"}})
    [row] = match_email(inp([LineIn("99999999", "99999999", "REMITTANCE", D("100"))]), w, RULES)
    assert (row.final_classification, row.score.decision, row.score.exception_reason, row.kunnr) == (
        "EXCEPTION", "EXCEPTION", "No BSID match found", "0000100001")
    [oos] = match_email(inp([], label="OUT_OF_SCOPE", out_of_scope_category="MARKETING"), w, RULES)
    assert (oos.final_classification, oos.score.status, oos.out_of_scope_reason) == ("OUT_OF_SCOPE", "IGNORED", "Marketing")


def test_unreferenced_payment_found_by_amount_always_reviewed():
    items = [item(i, f"9003{i:04d}", a) for i, a in enumerate([1000, 2500, 400, 3333.33, 120], start=1)]
    combos = find_combinations(D("2900"), items, tolerance_pct=0.5, max_invoices=6)
    assert [sorted(i.amount for i in c.items) for c in combos][0] == [D("400"), D("2500")]
    assert find_combinations(D("2900"), items, tolerance_pct=0.5, max_invoices=1) == []
    w = world(items, addresses={"ap@summit.com": {"0000100001"}})
    rows = match_email(inp([], total=D("2900"), payment_currency="USD"), w, RULES)
    assert len(rows) == 2 and all(r.match_type == "AMOUNT_COMBINATION" and r.score.status == "PENDING_REVIEW"
                                  for r in rows)
    [none] = match_email(inp([], total=D("7")), w, RULES)
    assert none.score.exception_reason == "No invoice reference found"


def test_combination_search_respects_tolerance_and_six_invoices():
    items = [item(i, f"9003{i:04d}", 100) for i in range(1, 9)]
    assert len(find_combinations(D("600"), items, tolerance_pct=0.5, max_invoices=6)[0].items) == 6
    assert find_combinations(D("700"), items, tolerance_pct=0.5, max_invoices=6) == []
    assert find_combinations(D("100.4"), items, tolerance_pct=0.5, max_invoices=6)[0].difference == D("-0.4")


def test_ptp_without_promise_date_goes_to_review():
    w = world([item(1, "90031344", 1150)], addresses={"ap@summit.com": {"0000100001"}})
    [row] = match_email(inp([LineIn("90031344", "90031344", "PTP", D("1150"))], label="PTP", contains_remittance=False),
                        w, RULES)
    assert row.assigned_role == "COLLECTIONS_ANALYST" and "Promise date missing" in row.score.review_reasons


# --------------------------------------------------------------------------- duplicates
def key(rid, email, *, amount="100.00", days=0, inv="90031280", dom="summit.com", hashes=(), kind="REMITTANCE"):
    return RowKey(rid, email, inv, "0000100001", D(amount), "USD", dom,
                  datetime(2026, 10, 20, tzinfo=timezone.utc) + timedelta(days=days), frozenset(hashes), kind)


def test_duplicate_rules():
    cfg = RULES["duplicate_detection"]
    old = key(1, "a")
    assert find_original(key("n", "b", days=3), [old], cfg)[0] is old
    assert find_original(key("n", "b", days=8), [old], cfg)[0] is None             # outside 7 days
    assert find_original(key("n", "b", amount="100.02"), [old], cfg)[0] is None    # more than 0.01 %
    assert find_original(key("n", "b", dom="other.com"), [old], cfg)[0] is None
    assert find_original(key("n", "a"), [old], cfg)[0] is None                     # same e-mail
    promise = key(2, "p", kind="PTP")                                               # P03 promise -> P03R payment
    assert find_original(key("n", "b"), [promise], cfg)[0] is None
    by_file = find_original(key("n", "b", days=30, hashes={"abc"}), [key(1, "a", hashes={"abc"})], cfg)
    assert by_file[0] is not None and "identical attachment" in by_file[1]


# --------------------------------------------------------------------------- database (laptop) end to end
@pytest.fixture(autouse=True)
def no_real_gmail(monkeypatch):
    from app.gmail import client

    monkeypatch.setattr(get_settings(), "poller_enabled", False)
    monkeypatch.setattr(client, "build_service", lambda *a, **k: (_ for _ in ()).throw(AssertionError("real Gmail")))


def processed(db, storage, code, gid, when=None):
    msg = build_message(load_sample(code), now=when or datetime(2026, 10, 27, 9, tzinfo=timezone.utc))
    e = store_email(db, msg.as_bytes(), storage=storage, gmail_id=gid)
    db.commit()
    parse_email(db, e, storage=storage)
    classify_email(db, e, model=None)
    extract_email(db, e)
    return e


def test_p03_0193_matches_customer_102419_sgd_8300(db, storage):
    e = processed(db, storage, "P03-0193", "m05-p03")
    [w] = match_stored_email(db, e)
    assert (w.invoice_ref_raw, w.kunnr, w.amount, w.currency, w.match_level) == (
        "JP-26-002271", "0000102419", D("8300.00"), "SGD", "EXACT")
    assert w.final_classification == "PTP" and w.decision == "AUTO_PROCESS" and e.status == "PROCESSED"
    assert w.confidence_score == max(D("92"), w.formula_confidence)
    assert w.confidence_source == ("FAST_PATH" if w.formula_confidence < 92 else "FORMULA")
    assert db.scalar(select(PtpCommitment).where(PtpCommitment.work_item_id == w.id)).promise_date == date(2026, 11, 27)
    assert db.scalar(select(MatchCandidate).where(MatchCandidate.work_item_id == w.id)).chosen


def test_resent_sample_becomes_duplicate(db, storage):
    first = processed(db, storage, "R10-0076", "m05-r1", datetime(2026, 10, 26, 9, tzinfo=timezone.utc))
    orig = match_stored_email(db, first)[0]  # R10-0076: not in the laptop database yet
    again = processed(db, storage, "R10-0076", "m05-r2", datetime(2026, 10, 27, 9, tzinfo=timezone.utc))
    dup = match_stored_email(db, again)[0]
    assert orig.final_classification == "REMITTANCE"
    assert (dup.final_classification, dup.status, dup.duplicate_of_id, dup.recommended_action) == (
        "DUPLICATE", "DUPLICATE", orig.id, "Close as Duplicate")


def test_rematching_the_original_repoints_its_duplicates(db, storage):
    first = processed(db, storage, "R10-0076", "m05-o1", datetime(2026, 10, 26, 9, tzinfo=timezone.utc))
    match_stored_email(db, first)
    again = processed(db, storage, "R10-0076", "m05-o2", datetime(2026, 10, 27, 9, tzinfo=timezone.utc))
    dup = match_stored_email(db, again)[0]
    new_orig = match_stored_email(db, first)[0]  # re-match the ORIGINAL: its rows are replaced
    db.refresh(dup)
    assert dup.duplicate_of_id == new_orig.id


def test_rematch_replaces_untouched_rows_but_not_worked_ones(db, storage):
    e = processed(db, storage, "R22-0128", "m05-r3")
    first = match_stored_email(db, e)
    again = match_stored_email(db, e)
    assert len(again) == len(first) and {w.id for w in again}.isdisjoint({w.id for w in first})
    again[0].status, again[0].resolved_at = "RESOLVED", datetime.now(timezone.utc)
    db.commit()
    with pytest.raises(AlreadyWorkedOn):
        match_stored_email(db, e)


def test_admin_match_endpoint(db, storage, monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_api_key", "k" * 20)
    app.dependency_overrides[get_db] = lambda: db
    try:
        c, h = TestClient(app), {"X-Admin-Key": "k" * 20}
        assert c.post("/api/admin/emails/EML-999999/match").status_code == 401
        assert c.post("/api/admin/emails/EML-999999/match", headers=h).status_code == 404
        e = store_email(db, build_message(load_sample("R12-0086")).as_bytes(), storage=storage, gmail_id="m05-api")
        db.commit()
        assert c.post(f"/api/admin/emails/{e.email_ref}/match", headers=h).status_code == 409
        parse_email(db, e, storage=storage)
        classify_email(db, e, model=None)
        extract_email(db, e)
        r = c.post(f"/api/admin/emails/{e.email_ref}/match", headers=h)
        body = r.json()
        assert r.status_code == 200 and body["work_items"][0]["decision"] == "MANUAL_REVIEW"  # found by amount
        assert "amount" not in body["work_items"][0]
        listed = next(i for i in c.get("/api/emails", params={"limit": 5}).json()["items"] if i["email_ref"] == e.email_ref)
        assert listed["work_items"] == {"MANUAL_REVIEW": 1}
    finally:
        app.dependency_overrides.pop(get_db, None)
