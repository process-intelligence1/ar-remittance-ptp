"""M04 extraction: lines (tables, aligned text, prose, SWIFT), header fields, currencies/FX, credits,
deductions, promises (relative / Japanese / instalments), mixed e-mails, saving, API."""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.classification.service import classify_email
from app.config import get_settings
from app.db import get_db
from app.documents.service import parse_email
from app.extraction.documents import ExtractionInput, Source, attachment_source, body_source
from app.extraction.extractor import extract
from app.extraction.service import NotClassifiedYet, current_extraction, extract_email
from app.gmail.parsing import clean_body
from app.gmail.poller import store_email
from app.gmail.sample_sender import build_message, load_sample
from app.main import app
from app.models.ar import AuditLog, Extraction, ExtractionLine

D = date(2026, 10, 28)  # e-mail date (a Wednesday)


def run(body: str = "", attachments: list[tuple[str, str, str, list | None]] = (), *, subject: str = "",
        rem: bool = True, ptp: bool = False, sender: str = "ap@customer.co.uk"):
    """attachments: (filename, parse_method, text, tables-rows or None)."""
    sources = [body_source(body, {"tables": []})]
    for name, method, text, rows in attachments:
        sources.append(attachment_source(f"att:{name}", name, method, text,
                                         {"tables": [{"rows": rows}] if rows else [], "pages": []}))
    label = "PTP" if ptp else "REMITTANCE"
    return extract(ExtractionInput(subject, sources, sender, D, D, label, rem, ptp))


def by_ref(result):
    return {l.ref_raw: l for l in result.lines}


# --------------------------------------------------------------------------- tables
def test_excel_table_with_currency_column():
    rows = [["REMITTANCE ADVICE"], ["Payment date:", "19 Oct 2026"], ["Payment reference:", "TRF42301241"],
            ["Invoice No.", "Invoice date", "Invoice amount", "Amount paid", "Currency"],
            ["UK-1043798", "2026-09-18", "4675.13", "4675.13", "GBP"], ["", "", "Total paid", "4675.13"]]
    r = run(attachments=[("advice.xlsx", "spreadsheet", "", rows)])
    [l] = r.lines
    assert (l.ref_raw, l.amount, l.gross, l.line_currency, l.invoice_date) == (
        "UK-1043798", Decimal("4675.13"), Decimal("4675.13"), "GBP", date(2026, 9, 18))
    assert (r.header.payment_reference, r.header.payment_date, r.header.total) == ("TRF42301241", date(2026, 10, 19),
                                                                                  Decimal("4675.13"))
    assert r.status == "OK" and r.total_mismatch == 0


def test_text_pdf_columns_with_blank_lines_between_header_and_rows():
    text = ("Payment date        2026-10-27\n\nInvoice No.          Invoice date        Invoice amount        Amount paid\n\n"
            "91005417             2026-09-09          21 607,00             21 607,00\n\n"
            "Total paid                               SEK 21 607,00\n")
    r = run(attachments=[("advice.pdf", "text", text, None)])
    [l] = r.lines
    assert (l.amount, l.payment_currency, l.method) == (Decimal("21607.00"), "SEK", "table")
    assert l.line_currency is None  # the document does not say the invoice's own currency


def test_ocr_header_typos_and_three_decimal_currency():
    rows = [["Involcg No.", "Involce date", "involce amount", "Amount pald"],
            ["MUM/2526/04179", "24/02/2026", "1,012.432", "1,012.432"], ["Total paid", "KD 1,012.432", "", ""]]
    r = run(attachments=[("scan.tif", "ocr", "", rows)])
    [l] = r.lines
    assert l.amount == Decimal("1012.432") and r.header.payment_currency == "KWD"


@pytest.mark.parametrize("written", ["-1,234.00", "1,234.00-", "(1,234.00)", "1,234.00 CR"])
def test_credit_note_lines_in_negative_formats(written):
    rows = [["Invoice No.", "Amount paid"], ["90031280", "5,000.00"], ["CN-1031273", written]]
    r = run(attachments=[("advice.docx", "docx", "", rows)])
    cn = by_ref(r)["CN-1031273"]
    assert cn.amount == Decimal("-1234.00") and cn.credit_note
    assert not by_ref(r)["90031280"].credit_note


def test_gross_deduction_net_with_reason():
    rows = [["Invoice No.", "Invoice amount", "TDS", "Amount paid"], ["MUM/2627/04398", "1,00,000.00", "2,000.00", "98,000.00"]]
    [l] = run(attachments=[("advice.pdf", "text", "", rows)]).lines
    assert (l.gross, l.deduction, l.amount, l.deduction_reason) == (
        Decimal("100000.00"), Decimal("2000.00"), Decimal("98000.00"), "TDS")


def test_invoice_currency_payment_currency_and_fx_rate_kept_apart():
    text = ("Please be advised that on 25 Oct 2026 we transferred US$9,757.59 in payment of the following invoice.\n"
            "Exchange rate: 1.2660\n")
    rows = [["Invoice No.", "Invoice date", "Invoice amount", "Amount paid"], ["Inv# UK-1043362", "06 May 2026", "£7,707.05", "9,757.59"]]
    r = run(attachments=[("advice.docx", "docx", text, rows)])
    [l] = r.lines
    assert (l.ref_raw, l.line_currency, l.gross, l.amount, l.payment_currency) == (
        "UK-1043362", "GBP", Decimal("7707.05"), Decimal("9757.59"), "USD")
    assert r.header.fx_rate == Decimal("1.2660") and r.header.total == Decimal("9757.59")


# --------------------------------------------------------------------------- prose / SWIFT / body tables
def test_prose_reference_with_amount_in_brackets():
    text = "on 19/10/2026 we transferred AUD 951.50 in payment of the following invoices: JP-26-002358 (AUD 951.50)."
    [l] = run(attachments=[("advice.docx", "docx", text, None)]).lines
    assert (l.amount, l.payment_currency, l.method) == (Decimal("951.50"), "AUD", "prose")


def test_swift_field_70_wrapped_over_two_lines():
    text = ("Amount                           JPY 750,585\nRemittance information (field 70)\n"
            "/INV/INV-JP-26-002727/568953/INV/JP\n-26-002880/181632\n")
    r = run(attachments=[("bank.pdf", "text", text, None)])
    assert {l.ref_raw: l.amount for l in r.lines} == {"JP-26-002727": Decimal("568953"), "JP-26-002880": Decimal("181632")}
    assert r.header.total == Decimal("750585") and r.total_mismatch == 0


def test_body_column_table_with_inv_prefix():
    body = "Please note the payment below:\n\nInvoice No.            Amount paid\nInv# UK-1043514        GBP 1,707.60\nUK-1043671             GBP 1,673.51\n"
    r = run(body)
    assert {l.ref_raw: l.amount for l in r.lines} == {"UK-1043514": Decimal("1707.60"), "UK-1043671": Decimal("1673.51")}


def test_same_invoice_in_subject_body_and_attachment_is_one_line():
    rows = [["Invoice No.", "Amount paid"], ["90031280", "6,400.00"]]
    r = run("Payment for invoice 90031280 attached.", [("ra.pdf", "text", "", rows)], subject="Payment for invoice 90031280")
    [l] = r.lines
    assert l.amount == Decimal("6400.00") and l.method == "table"
    assert {a["method"] for a in l.evidence["also_found"]} == {"mention"}


# --------------------------------------------------------------------------- header
def test_header_customer_number_iban_references_and_rem():
    text = ("Ordering customer            Cardiff Bay Marine Services Ltd\n"
            "Debit account             GB16BARC67159787225212\n"
            "Your customer no.:  101114\nOur reference: OR-5521\nYour reference: PO 4410\n"
            "Remittance REM-2026-00042 for invoice UK-1043976\n")
    h = run(attachments=[("bank.pdf", "text", text, None)]).header
    assert (h.payer_name, h.payer_account, h.customer_number) == ("Cardiff Bay Marine Services Ltd", "GB16BARC67159787225212", "101114")
    assert (h.our_reference, h.your_reference, h.remittance_refs) == ("OR-5521", "PO 4410", ["REM-2026-00042"])
    assert h.evidence["payer_account"]["label"] == "IBAN"


def test_german_labels_and_today():
    body = "wir haben heute 4.600,00 EUR fuer Rechnung 91005442 ueberwiesen.\nIhre Kunden-Nr.: 100889\n"
    r = run(body)
    assert (r.header.customer_number, r.header.payment_date, r.header.total) == ("100889", D, Decimal("4600.00"))
    assert r.header.evidence["payment_date"]["note"].startswith('"today"')


# --------------------------------------------------------------------------- promises
@pytest.mark.parametrize("wording, expected", [
    ("next Friday", date(2026, 10, 30)), ("end of month", date(2026, 10, 31)), ("within 7 days", date(2026, 11, 4)),
])
def test_relative_promise_date_against_email_date_with_wording(wording, expected):
    r = run(f"We will pay invoice 90031344 for USD 1,150.00 {wording}.", rem=False, ptp=True)
    [l] = r.lines
    assert (l.line_type, l.promise_date, l.promise_text) == ("PTP", expected, wording)


@pytest.mark.parametrize("written", ["2026年11月27日", "令和8年11月27日"])
def test_japanese_promise_dates(written):
    r = run(f"請求書JP-26-002366（1,402,390円）につきまして、{written}にお振込み予定でございます。", rem=False, ptp=True)
    [l] = r.lines
    assert (l.promise_date, l.amount, l.payment_currency) == (date(2026, 11, 27), Decimal("1402390"), "JPY")


def test_instalment_plan_becomes_one_line_per_instalment():
    body = ("Further to your reminder, we propose to settle invoice SI42600379 (GBP 12,528.00) in instalments:\n"
            "  - 28 Oct 2026: GBP 4,176.00\n  - 27 Nov 2026: GBP 4,176.00\n  - 27 Dec 2026: GBP 4,176.00\n")
    lines = run(body, rem=False, ptp=True).lines
    assert [(l.instalment_no, l.promise_date, l.amount) for l in lines] == [
        (1, date(2026, 10, 28), Decimal("4176.00")), (2, date(2026, 11, 27), Decimal("4176.00")),
        (3, date(2026, 12, 27), Decimal("4176.00"))]
    assert lines[0].gross == Decimal("12528.00") and {l.ref_raw for l in lines} == {"SI42600379"}


def test_mixed_email_remittance_and_promise_lines():
    body = ("wir haben folgende Zahlung veranlasst:\n\nRechnungs-Nr.          Zahlbetrag\n  91005413             2.856,00 EUR\n\n"
            "Die restlichen Rechnungen 91005384 begleichen wir am 13. November 2026.\n")
    r = run(body, rem=True, ptp=True)
    paid, promised = by_ref(r)["91005413"], by_ref(r)["91005384"]
    assert (paid.line_type, paid.amount, paid.promise_date) == ("REMITTANCE", Decimal("2856.00"), None)
    assert (promised.line_type, promised.promise_date) == ("PTP", date(2026, 11, 13))


def test_quoted_reply_history_is_not_extracted_twice():
    raw = ("Paid invoice 90031280, USD 6,400.00 today.\n\nOn Mon, 26 Oct 2026 at 10:00, AR Team <ar@acme.com> wrote:\n"
           "> Reminder: invoice 90031280 and 90031281 are overdue.\n")
    lines = run(clean_body(raw)).lines
    assert [l.ref_raw for l in lines] == ["90031280"]


def test_instalment_list_is_not_mistaken_for_reply_history():
    body = clean_body("Hello,\n\nwe propose to settle invoice SI42600379 in instalments:\n  - 28 Oct 2026: GBP 4,176.00\n")
    assert "28 Oct 2026" in body


# --------------------------------------------------------------------------- checks
def test_total_mismatch_is_reported():
    rows = [["Invoice No.", "Amount paid"], ["90031280", "100.00"], ["90031281", "50.00"], ["Total paid", "200.00"]]
    r = run(attachments=[("ra.pdf", "text", "", rows)])
    assert r.total_mismatch == Decimal("50.00") and any("differs" in w for w in r.warnings)


def test_out_of_scope_and_no_lines():
    inp = ExtractionInput("Newsletter", [body_source("Unsubscribe", {})], label="OUT_OF_SCOPE",
                          contains_remittance=False)
    assert extract(inp).status == "SKIPPED"
    assert run("wir haben heute 4.600,00 EUR ueberwiesen.").status == "NO_LINES"


# --------------------------------------------------------------------------- saving (laptop database)
@pytest.fixture(autouse=True)
def no_real_gmail(monkeypatch):
    from app.gmail import client

    monkeypatch.setattr(get_settings(), "poller_enabled", False)
    monkeypatch.setattr(client, "build_service", lambda *a, **k: (_ for _ in ()).throw(AssertionError("real Gmail")))


def _ready(db, storage, code: str, gid: str):
    e = store_email(db, build_message(load_sample(code)).as_bytes(), storage=storage, gmail_id=gid)
    db.commit()
    parse_email(db, e, storage=storage)
    return e


def test_extract_email_saves_lines_status_audit_and_history(db, storage):
    e = _ready(db, storage, "P06-0208", "m04-t1")  # body only: payment + promise
    with pytest.raises(NotClassifiedYet):
        extract_email(db, e)
    classify_email(db, e, model=None)
    extract_email(db, e)
    x = current_extraction(db, e.id)
    lines = db.scalars(select(ExtractionLine).where(ExtractionLine.extraction_id == x.id).order_by(ExtractionLine.line_no)).all()
    assert e.status == "EXTRACTED" and x.status in ("OK", "PARTIAL") and x.lines_count == len(lines) == 4
    assert {l.invoice_ref_norm: l.line_type for l in lines}["91005384"] == "PTP"
    assert x.total_amount == Decimal("15731.88") and x.total_mismatch == 0 and x.payment_reference == "E2E-7912734035"
    assert db.scalar(select(AuditLog).where(AuditLog.entity_id == e.email_ref, AuditLog.action == "EMAIL_EXTRACTED"))
    extract_email(db, e)
    assert len(db.scalars(select(Extraction).where(Extraction.email_id == e.id)).all()) == 2


def test_admin_extract_endpoint(db, storage, monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_api_key", "k" * 20)
    app.dependency_overrides[get_db] = lambda: db
    try:
        c, h = TestClient(app), {"X-Admin-Key": "k" * 20}
        assert c.post("/api/admin/emails/EML-999999/extract").status_code == 401
        assert c.post("/api/admin/emails/EML-999999/extract", headers=h).status_code == 404
        e = _ready(db, storage, "R13-0091", "m04-t2")
        assert c.post(f"/api/admin/emails/{e.email_ref}/extract", headers=h).status_code == 409  # not classified
        classify_email(db, e, model=None)
        r = c.post(f"/api/admin/emails/{e.email_ref}/extract", headers=h)
        assert r.status_code == 200 and r.json()["extraction"]["status"] == "NO_LINES"  # R13: no invoice numbers
        listed = c.get("/api/emails", params={"limit": 5}).json()["items"]
        mine = next(i for i in listed if i["email_ref"] == e.email_ref)
        assert mine["extraction"]["lines"] == 0 and "total" not in mine["extraction"]  # counts only, no amounts
    finally:
        app.dependency_overrides.pop(get_db, None)
