"""Extract a stored e-mail (after M03 classification) and save ar.extraction + ar.extraction_line.

Input: body_text_clean (quoted reply history removed, so it is not extracted twice) + its tables,
and every parsed, non-inline attachment (text, tables, word boxes). Older runs are kept with
is_current = false. E-mail status CLASSIFIED -> EXTRACTED; audit entry EMAIL_EXTRACTED.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.classification.service import current_classification
from app.extraction.documents import ExtractionInput, attachment_source, body_source
from app.extraction.extractor import ExtractionResult, extract
from app.extraction.llm import maybe_improve
from app.gmail.poller import current_business_date
from app.models.ar import AuditLog, EmailAttachment, EmailMessage, Extraction, ExtractionLine, RuleConfig
from app.rules_defaults import EXTRACTION

EXTRACTABLE = ("CLASSIFIED", "EXTRACTED", "PROCESSED")


class NotClassifiedYet(Exception):
    """M03 has not classified this e-mail yet."""


def rule_config(db: Session) -> dict:
    row = db.get(RuleConfig, "extraction")
    return {**EXTRACTION, **(row.value if row and isinstance(row.value, dict) else {})}


def input_for_email(db: Session, email: EmailMessage) -> ExtractionInput:
    cls = current_classification(db, email.id)
    if cls is None:
        raise NotClassifiedYet(f"{email.email_ref} has not been classified yet - run M03 first")
    sources = [body_source(email.body_text_clean or email.body_text or "", email.body_layout)]
    atts = db.scalars(select(EmailAttachment).where(EmailAttachment.email_id == email.id,
                                                    EmailAttachment.is_inline.is_(False),
                                                    EmailAttachment.parse_status == "PARSED")
                      .order_by(EmailAttachment.id)).all()
    for a in atts:
        sources.append(attachment_source(f"att:{a.id}", a.filename, a.parse_method, a.text_content, a.layout, a.id))
    bd = email.business_date or current_business_date(db)
    email_date: date = email.received_at.date() if email.received_at else bd
    return ExtractionInput(subject=email.subject or "", sources=sources, sender_email=email.sender_email,
                           email_date=email_date, business_date=bd, label=cls.label,
                           contains_remittance=cls.contains_remittance, contains_ptp=cls.contains_ptp)


def _json(value):
    """Evidence may hold dates / decimals: make it JSON-safe."""
    if isinstance(value, dict):
        return {k: _json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(v) for v in value]
    if isinstance(value, (date, Decimal)):
        return str(value)
    return value


def save(db: Session, email: EmailMessage, r: ExtractionResult) -> Extraction:
    db.execute(update(Extraction).where(Extraction.email_id == email.id, Extraction.is_current.is_(True))
               .values(is_current=False))
    h = r.header
    ext = Extraction(
        email_id=email.id, is_current=True, status=r.status, method="rules", payer_name=h.payer_name,
        sender_domain=email.sender_domain, customer_number=h.customer_number, payer_account=h.payer_account,
        our_reference=h.our_reference, your_reference=h.your_reference, payment_reference=h.payment_reference,
        advice_number=h.advice_number, remittance_refs=h.remittance_refs or None, payment_date=h.payment_date,
        promise_date=h.promise_date, promise_text=(h.promise_text or None) and h.promise_text[:200],
        total_amount=h.total, payment_currency=h.payment_currency, fx_rate=h.fx_rate,
        document_currency=r.doc_currency, lines_count=len(r.lines), lines_sum=r.lines_sum,
        total_mismatch=r.total_mismatch, warnings=r.warnings or None, evidence=_json(h.evidence))
    db.add(ext)
    db.flush()
    for n, ln in enumerate(r.lines, start=1):
        db.add(ExtractionLine(
            extraction_id=ext.id, line_no=n, line_type=ln.line_type or "REMITTANCE", invoice_ref_raw=ln.ref_raw[:60],
            invoice_ref_norm=(ln.ref_norm or "")[:60] or None, amount=ln.amount, gross_amount=ln.gross,
            deduction_amount=ln.deduction, deduction_reason=ln.deduction_reason, line_currency=ln.line_currency,
            payment_currency=ln.payment_currency,
            fx_rate=h.fx_rate if ln.line_currency and ln.payment_currency and ln.line_currency != ln.payment_currency else None,
            credit_note_flag=ln.credit_note, invoice_date=ln.invoice_date, promise_date=ln.promise_date,
            promise_text=(ln.promise_text or None) and ln.promise_text[:200], instalment_no=ln.instalment_no,
            method=ln.method, source_kind=ln.source.kind, source_name=ln.source.name[:300],
            attachment_id=ln.source.attachment_id, evidence=_json(ln.evidence)))
    return ext


def extract_email(db: Session, email: EmailMessage) -> ExtractionResult:
    if email.status not in EXTRACTABLE:
        raise NotClassifiedYet(f"{email.email_ref} is {email.status} - it must be read (M02) and classified (M03) first")
    inp = input_for_email(db, email)
    result = maybe_improve(extract(inp), rule_config(db))
    ext = save(db, email, result)
    if email.status == "CLASSIFIED":
        email.status = "EXTRACTED"
    db.add(AuditLog(business_date=current_business_date(db), actor="system", entity_type="email",
                    entity_id=email.email_ref, action="EMAIL_EXTRACTED",
                    details={"status": result.status, "lines": len(result.lines), "total": str(result.header.total)
                             if result.header.total is not None else None, "currency": result.header.payment_currency,
                             "warnings": result.warnings or None, "extraction_id": ext.id}))
    db.commit()
    return result


def current_extraction(db: Session, email_id: int) -> Extraction | None:
    return db.scalar(select(Extraction).where(Extraction.email_id == email_id, Extraction.is_current.is_(True)))
