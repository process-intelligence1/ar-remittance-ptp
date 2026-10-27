"""Build the matcher's input from an in-memory extraction (samples / evaluation) or from the stored
ar.extraction + ar.extraction_line rows (database)."""
from datetime import date, datetime

from app.extraction.documents import ExtractionInput
from app.extraction.extractor import ExtractionResult
from app.matching.matcher import LineIn, MatchInput
from app.models.ar import EmailMessage, Extraction, ExtractionLine


def from_result(email_key, inp: ExtractionInput, r: ExtractionResult, *, out_of_scope_category: str | None,
                received_at: datetime | None, business_date: date, sender_name: str | None = None) -> MatchInput:
    h = r.header
    lines = [LineIn(l.ref_raw, l.ref_norm, l.line_type or "REMITTANCE", l.amount, l.gross, l.deduction,
                    l.deduction_reason, l.line_currency, l.payment_currency, l.credit_note, l.invoice_date,
                    l.promise_date, l.promise_text, l.instalment_no, l.method, l.evidence) for l in r.lines]
    return MatchInput(email_key=email_key, label=inp.label or "REMITTANCE", out_of_scope_category=out_of_scope_category,
                      contains_remittance=inp.contains_remittance, sender_email=inp.sender_email, sender_name=sender_name,
                      received_at=received_at, email_date=inp.email_date, business_date=business_date,
                      attachments=sum(1 for s in inp.sources if s.kind != "body"), lines=lines,
                      payer_name=h.payer_name, customer_number=h.customer_number, payer_account=h.payer_account,
                      payment_reference=h.payment_reference or h.advice_number, remittance_refs=h.remittance_refs,
                      payment_date=h.payment_date, total=h.total, payment_currency=h.payment_currency)


def from_db(email: EmailMessage, x: Extraction, lines: list[ExtractionLine], *, label: str, out_of_scope_category: str | None,
            contains_remittance: bool, attachments: int, business_date: date) -> MatchInput:
    ins = [LineIn(l.invoice_ref_raw, l.invoice_ref_norm, l.line_type, l.amount, l.gross_amount, l.deduction_amount,
                  l.deduction_reason, l.line_currency, l.payment_currency, l.credit_note_flag, l.invoice_date,
                  l.promise_date, l.promise_text, l.instalment_no, l.method, l.evidence, l.id) for l in lines]
    refs = x.remittance_refs or []
    return MatchInput(email_key=email.id, label=label, out_of_scope_category=out_of_scope_category,
                      contains_remittance=contains_remittance, sender_email=email.sender_email,
                      sender_name=email.sender_name, received_at=email.received_at,
                      email_date=email.received_at.date() if email.received_at else business_date,
                      business_date=email.business_date or business_date, attachments=attachments, lines=ins,
                      payer_name=x.payer_name, customer_number=x.customer_number, payer_account=x.payer_account,
                      payment_reference=x.payment_reference or x.advice_number or (refs[0] if refs else None),
                      remittance_refs=refs, payment_date=x.payment_date, total=x.total_amount,
                      payment_currency=x.payment_currency)
