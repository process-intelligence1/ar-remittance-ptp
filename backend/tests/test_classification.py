"""M03 classification: text folding, dates, rules, model hand-off, expected answers, saving, API."""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.emails import _classification_summary
from app.classification.classifier import classify
from app.classification.inputs import ClassifierInput, Document
from app.classification.model import train
from app.classification.rules import from_key
from app.classification.samples import expected_for
from app.classification.service import NotReadYet, classify_email, current_classification, sender_known
from app.classification.signals import find_dates, fold
from app.config import get_settings
from app.db import get_db
from app.documents.service import parse_email
from app.gmail.poller import store_email
from app.gmail.sample_sender import build_message, load_sample
from app.main import app
from app.models.ar import AuditLog, EmailClassification
from app.models.sap import Adr6

BD = date(2026, 10, 28)


@pytest.fixture(autouse=True)
def no_real_gmail(monkeypatch):
    """conftest switches POLLER_ENABLED on for every test; here that would make the label step build a
    REAL Gmail connection. Switch it off and make any real connection attempt fail loudly."""
    from app.gmail import client

    monkeypatch.setattr(get_settings(), "poller_enabled", False)

    def refuse(*args, **kwargs):
        raise AssertionError("test tried to open the real Gmail mailbox")

    monkeypatch.setattr(client, "build_service", refuse)


def rules(subject: str, body: str, attachments: list[Document] | None = None, **kw):
    """Rules only (no model), so results do not depend on the trained model file."""
    return classify(ClassifierInput(subject, body, attachments or [], business_date=BD, **kw), model=None)


# --------------------------------------------------------------------------- folding and dates
def test_fold_writes_out_umlauts_and_drops_accents_but_keeps_japanese():
    assert fold("Überweisung GRÜSSE ß") == "ueberweisung gruesse ss"
    assert fold("Règlement effectué, Ação") == "reglement effectue, acao"
    assert fold("お振込みのご連絡") == "お振込みのご連絡"  # kana marks must survive
    assert fold("ＲＥＭＩＴＴＡＮＣＥ") == "remittance"   # full-width letters


def test_find_dates_keeps_both_readings_of_ambiguous_dates():
    found = dict(find_dates(fold("am 13.11.2026, on 03/11/2026, 18 Nov 2026, November 2, 2026, 2026年11月5日")))
    assert found["13.11.2026"] == [date(2026, 11, 13)]
    assert found["03/11/2026"] == [date(2026, 3, 11), date(2026, 11, 3)]
    assert found["18 nov 2026"] == [date(2026, 11, 18)]
    assert found["november 2, 2026"] == [date(2026, 11, 2)]
    assert found["2026年11月5日"] == [date(2026, 11, 5)]


# --------------------------------------------------------------------------- rules
def test_remittance_advice_english():
    r = rules("Remittance advice", "Please find attached our remittance advice for the payment made today.",
              [Document("Remittance_Advice_ZA-1.pdf", "REMITTANCE ADVICE Invoice No. 90031280 Amount paid USD 6,400.00")])
    assert (r.label, r.contains_remittance, r.contains_ptp) == ("REMITTANCE", True, False)
    assert r.confidence >= 90 and r.method == "rules"
    assert {"remittance advice", "advice file"} <= {s["signal"] for s in r.reasons["signals"]}
    assert "90031280" in r.reasons["evidence"]["invoice_refs"]


@pytest.mark.parametrize("subject, body", [
    ("Zahlungszusage", "Wir werden die Rechnung 91004754 ueber 4.153,10 EUR bis zum 19.11.2026 begleichen."),
    ("Compromiso de pago", "realizaremos el pago de la factura FA2026-08987 el 09/11/2026."),
    ("お支払い予定日のご連絡", "請求書JP-26-002500につきまして、2026/11/02にお振込み予定でございます。"),
    ("Re: reminder", "Payment of USD 10,117.39 for 90039201 is scheduled for 2026-11-04."),
])
def test_promise_to_pay_in_several_languages(subject, body):
    r = rules(subject, body)
    assert (r.label, r.contains_remittance, r.contains_ptp) == ("PTP", False, True)


def test_dots_inside_amounts_and_dates_do_not_break_a_phrase():
    r = rules("Erinnerung", "wir werden den Betrag von 3.300,00 EUR fuer Rechnung 91005123 am 15.11.2026 ueberweisen.")
    assert r.label == "PTP"


def test_payment_and_promise_in_one_email_sets_both_flags():
    r = rules("Zahlungsavis", "wir haben folgende Zahlung veranlasst: 91005413 2.856,00 EUR. "
                              "Die restlichen Rechnungen 91005384 begleichen wir am 13. November 2026.")
    assert (r.label, r.contains_remittance, r.contains_ptp) == ("PTP", True, True)  # both_label = PTP


def test_first_instalment_paid_is_a_remittance_not_a_promise():
    r = rules("Remittance details attached", "Please find attached our remittance advice for the payment made "
                                             "today.\nFirst instalment - balance to follow.")
    assert (r.label, r.contains_ptp) == ("REMITTANCE", False)


def test_future_tense_funds_is_not_a_payment():
    r = rules("Re: statement", "We expect to pay invoice 90031777 by 20 November 2026 once our funds are released.")
    assert (r.label, r.contains_remittance) == ("PTP", False)


@pytest.mark.parametrize("subject, body, category", [
    ("October highlights", "Dear Subscriber, 20% early-bird discount. Register now. Unsubscribe", "MARKETING"),
    ("Damaged goods - invoice 90031350", "The shipment for invoice 90031350 arrived damaged. Please arrange a replacement.",
     "CUSTOMER_SERVICE"),
    ("RFQ - 500 units", "Please quote for 500 units of item ACM-4410 and confirm lead time.", "SALES_INQUIRY"),
    ("Invitation", "Join our year-end meetup. Please reply to confirm attendance.", "GENERAL"),
    ("Invoice SINV-1 from Orbit", "Dear Customer, please find attached invoice SINV-1 for USD 1,649.36, due within 30 days.",
     "VENDOR_INVOICE"),
    ("Query on September payslip", "Dear HR Team, please find my details below.", "HR"),
    ("Your monthly statement is ready", "Your e-statement is available in online banking. Automated message.",
     "BANK_NOTIFICATION"),
])
def test_out_of_scope_categories(subject, body, category):
    r = rules(subject, body)
    assert (r.label, r.out_of_scope_category, r.contains_remittance, r.contains_ptp) == ("OUT_OF_SCOPE", category, False, False)


def test_dispute_that_says_we_will_not_pay_is_not_a_promise():
    r = rules("Query on invoice 90031888", "The unit price does not match our purchase order. Can your service team "
                                           "check it? We will not pay until this is resolved.")
    assert r.label == "OUT_OF_SCOPE" and r.out_of_scope_category == "CUSTOMER_SERVICE"


def test_nothing_recognised_is_out_of_scope_with_low_confidence():
    r = rules("Hello", "Just checking in.")
    assert (r.label, r.out_of_scope_category) == ("OUT_OF_SCOPE", "GENERAL")
    assert r.confidence < 30 and r.reasons["note"].startswith("No remittance")


# --------------------------------------------------------------------------- model hand-off
class FakeModel:
    def __init__(self, key: str, p: float):
        self.answer = [(key, p), ("REMITTANCE", 1 - p)]

    def predict(self, inp):
        return self.answer


def _weak_input():  # one weak hint only -> rules unsure
    return ClassifierInput("Info", "Payment reference 12345, USD 100.00", business_date=BD)


def test_model_not_asked_when_rules_are_sure():
    r = classify(ClassifierInput("Remittance advice", "We have paid invoice 90031280.", business_date=BD),
                 model=FakeModel("PTP", 0.99))
    assert r.method == "rules" and r.label == "REMITTANCE" and "model" not in r.reasons


def test_sure_model_overrides_unsure_rules():
    r = classify(_weak_input(), model=FakeModel("PTP", 0.9))
    assert (r.label, r.method, r.confidence) == ("PTP", "rules+model", 90.0)
    assert r.reasons["model"]["decision"].startswith("model answer used")


def test_unsure_model_keeps_the_rules_answer():
    r = classify(_weak_input(), model=FakeModel("PTP", 0.4))
    assert r.label == "REMITTANCE" and r.reasons["model"]["decision"].startswith("rules answer kept")  # weak, has an amount


def test_model_answer_used_when_rules_found_no_wording():
    r = classify(ClassifierInput("Hi", "Invoice 90031501 USD 780.00 done.", business_date=BD),
                 model=FakeModel("REMITTANCE", 0.45))
    assert (r.label, r.confidence) == ("REMITTANCE", 45.0) and "no wording" in r.reasons["model"]["decision"]


def test_mixed_key_round_trip():
    assert from_key("MIXED") == ("PTP", True, True, None)
    assert from_key("OUT_OF_SCOPE:HR") == ("OUT_OF_SCOPE", False, False, "HR")


def test_tiny_model_trains_and_predicts():
    texts = ["remittance advice amount paid"] * 3 + ["we will pay on 10 nov"] * 3
    m = train(texts, ["REMITTANCE"] * 3 + ["PTP"] * 3)
    assert m.predict(ClassifierInput("", "we will pay on 12 nov"))[0][0] == "PTP"


# --------------------------------------------------------------------------- expected answers
@pytest.mark.parametrize("code, key", [
    ("R01-0007", "REMITTANCE"), ("P01-0178", "PTP"), ("P06-0208", "MIXED"),
    ("P03R-0194", "REMITTANCE"), ("P05R-0202", "REMITTANCE"),
    ("O01-0218", "OUT_OF_SCOPE:MARKETING"), ("O05-0228", "OUT_OF_SCOPE:VENDOR_INVOICE"),
    ("O07-0233", "OUT_OF_SCOPE:BANK_NOTIFICATION"),
])
def test_expected_answer_from_folder_prefix(code, key):
    assert expected_for(code).key == key


# --------------------------------------------------------------------------- saving (laptop database)
def _stored(db, storage, code: str, gmail_id: str):
    e = store_email(db, build_message(load_sample(code)).as_bytes(), storage=storage, gmail_id=gmail_id)
    db.commit()
    return e


def test_classify_email_saves_result_status_and_audit(db, storage):
    e = _stored(db, storage, "P06-0208", "m03-t1")  # body only: remittance + promise
    with pytest.raises(NotReadYet):
        classify_email(db, e, model=None)
    parse_email(db, e, storage=storage)
    r = classify_email(db, e, model=None)
    c = current_classification(db, e.id)
    assert (c.label, c.contains_remittance, c.contains_ptp, c.method) == ("PTP", True, True, "rules")
    assert e.status == "CLASSIFIED" and float(c.confidence) == r.confidence
    audit = db.scalar(select(AuditLog).where(AuditLog.entity_id == e.email_ref, AuditLog.action == "EMAIL_CLASSIFIED"))
    assert audit.details["label"] == "PTP" and audit.details["gmail_label"] is None  # laptop: no Gmail


def test_reclassify_keeps_history(db, storage):
    e = _stored(db, storage, "O01-0218", "m03-t2")
    parse_email(db, e, storage=storage)
    classify_email(db, e, model=None)
    classify_email(db, e, model=None)
    rows = db.scalars(select(EmailClassification).where(EmailClassification.email_id == e.id)).all()
    assert len(rows) == 2 and sum(r.is_current for r in rows) == 1


def test_gmail_label_is_set_and_old_one_removed(db, storage, fake_service):
    e = _stored(db, storage, "O01-0218", "m03-t3")
    gid = fake_service.gmail.add_raw(b"x")
    e.gmail_id = gid
    parse_email(db, e, storage=storage)
    fake_service.gmail.messages[gid]["labelIds"].append("Label_X")
    classify_email(db, e, gmail_service=fake_service, model=None)
    assert "AR-OutOfScope" in fake_service.gmail.label_names(gid)
    assert not {"AR-Remittance", "AR-PTP"} & fake_service.gmail.label_names(gid)


def test_sender_known_by_address_or_company_domain(db):
    addr = db.scalar(select(Adr6.smtp_addr).where(Adr6.smtp_addr.is_not(None)).limit(1))
    if addr is None:
        pytest.skip("no ADR6 data in the laptop database")
    assert sender_known(db, addr.upper())
    assert sender_known(db, "someone.else@" + addr.split("@")[1]) == (addr.split("@")[1] not in ("gmail.com",))
    assert not sender_known(db, "nobody@unknown-company.example")
    assert not sender_known(db, None)


def test_api_summary_has_signal_names_but_no_email_text(db, storage):
    e = _stored(db, storage, "P06-0208", "m03-t4")
    parse_email(db, e, storage=storage)
    classify_email(db, e, model=None)
    s = _classification_summary(current_classification(db, e.id))
    assert s["label"] == "PTP" and s["signals"] and all("text" not in sig for sig in s["signals"])


def test_admin_classify_endpoint(db, storage, monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_api_key", "k" * 20)
    app.dependency_overrides[get_db] = lambda: db
    try:
        c = TestClient(app)
        h = {"X-Admin-Key": "k" * 20}
        assert c.post("/api/admin/emails/EML-999999/classify").status_code == 401
        assert c.post("/api/admin/emails/EML-999999/classify", headers=h).status_code == 404
        e = _stored(db, storage, "O03-0224", "m03-t5")
        assert c.post(f"/api/admin/emails/{e.email_ref}/classify", headers=h).status_code == 409  # not read yet
        parse_email(db, e, storage=storage)
        r = c.post(f"/api/admin/emails/{e.email_ref}/classify", headers=h)
        assert r.status_code == 200 and r.json()["classification"]["out_of_scope_category"] == "SALES_INQUIRY"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_weak_hint_without_any_reference_is_out_of_scope():
    r = rules("AR - AP usecases", "See the attached ideas.", [Document("ideas.html", "Each payment reference is checked.")])
    assert (r.label, r.confidence) == ("OUT_OF_SCOPE", 20.0) and r.reasons["note"].startswith("Only weak hints")


def test_document_about_ar_is_out_of_scope_and_low_confidence():
    text = ("Remittance advice. Amount paid 100.00 USD for 90031280. We will pay the rest on 10 Nov 2026. "
            "Newsletter: unsubscribe. RFQ: please quote. Payslip questions to the HR team.")
    r = classify(ClassifierInput("Remittance prototype", "", [Document("dataset.xlsx", text)], business_date=BD),
                 model=FakeModel("REMITTANCE", 0.99))
    assert (r.label, r.confidence, r.method) == ("OUT_OF_SCOPE", 30.0, "rules")
    assert "document about AR" in r.reasons["note"]


def test_model_not_asked_when_there_is_nothing_to_read():
    r = classify(ClassifierInput("", "Hi", [Document("page.html", "")], business_date=BD), model=FakeModel("PTP", 0.99))
    assert r.label == "OUT_OF_SCOPE" and r.method == "rules" and r.reasons["note"].startswith("Too little")


@pytest.mark.parametrize("n_classes", [2, 3])
def test_numpy_prediction_equals_scikit_learn(n_classes):
    """The image has no scikit-learn: model.npz is predicted with numpy. Same numbers as scikit-learn."""
    np = pytest.importorskip("numpy")
    from app.classification.model import build_pipeline, export

    texts = ["remittance advice amount paid 90031280 usd 6,400.00", "zahlungsavis ueberweisung zahlbetrag",
             "we will pay invoice 90031344 on nov 18", "wir werden die rechnung begleichen",
             "請求書jp-26-002366 お振込み予定でございます", "unsubscribe newsletter early-bird a b",
             "remittance advice payment made today", "payment commitment is scheduled for"]
    keys = (["REMITTANCE", "REMITTANCE", "PTP", "PTP", "PTP", "OUT_OF_SCOPE:MARKETING", "REMITTANCE", "PTP"]
            if n_classes == 3 else ["REMITTANCE", "REMITTANCE", "PTP", "PTP", "PTP", "REMITTANCE", "REMITTANCE", "PTP"])
    pipe = build_pipeline()
    pipe.fit(texts, keys)
    ours = export(pipe, len(texts))
    probe = ["Remittance advice for invoice 90031280", "お支払い予定 x", "we will pay", "", "a"]
    assert np.allclose(pipe.predict_proba(probe), [ours.probabilities(t) for t in probe], atol=1e-9)


def test_saved_model_loads_without_pickle(tmp_path):
    from app.classification.model import load_model, save

    m = train(["remittance advice amount paid"] * 3 + ["we will pay on 10 nov"] * 3, ["REMITTANCE"] * 3 + ["PTP"] * 3)
    save(m, tmp_path / "m.npz")
    loaded = load_model(tmp_path / "m.npz")
    assert loaded.classes == m.classes and loaded.predict(ClassifierInput("", "we will pay"))[0][0] == "PTP"
