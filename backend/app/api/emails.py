"""E-mails received (metadata only), a manual Gmail poll, reading (M02) and classification (M03).

Until the demo login exists (M08) these endpoints show NO e-mail bodies and NO files -
only references, senders, subjects, dates, attachment names/sizes/hashes and the classification
(signal NAMES only - the matched text snippets stay in the database).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.security import require_admin_key
from app.db import get_db
from app.gmail.client import GmailNotConfigured
from app.gmail.poller import PollAlreadyRunning, PollerDisabled, poll
from app.models.ar import EmailAttachment, EmailClassification, EmailMessage

router = APIRouter(prefix="/api", tags=["E-mails"])
admin = APIRouter(prefix="/api/admin", tags=["Admin"], dependencies=[Depends(require_admin_key)])


def _classification_summary(c: EmailClassification | None) -> dict | None:
    if c is None:
        return None
    reasons = c.reasons or {}
    return {"label": c.label, "contains_remittance": c.contains_remittance, "contains_ptp": c.contains_ptp,
            "out_of_scope_category": c.out_of_scope_category, "confidence": c.confidence, "method": c.method,
            "signals": [{k: v for k, v in sig.items() if k != "text"} for sig in reasons.get("signals", [])],
            "model": {k: v for k, v in (reasons.get("model") or {}).items() if k in ("answer", "probability", "decision")}
            or None,
            "classified_at": c.created_at}


def _email_summary(e: EmailMessage, atts: list[EmailAttachment], cls: EmailClassification | None = None) -> dict:
    return {
        "email_ref": e.email_ref, "source": e.source, "sample_code": e.sample_code,
        "gmail_id": e.gmail_id, "sender_email": e.sender_email, "sender_name": e.sender_name,
        "from_email": e.from_email, "is_forwarded": e.is_forwarded, "sender_domain": e.sender_domain,
        "subject": e.subject, "received_at": e.received_at, "business_date": e.business_date,
        "status": e.status, "error": e.error, "created_at": e.created_at, "language": e.language,
        "body_tables": len((e.body_layout or {}).get("tables", [])),
        "classification": _classification_summary(cls),
        "attachments": [
            {"id": a.id, "parent_id": a.parent_id, "depth": a.depth, "filename": a.filename,
             "mime_type": a.mime_type, "size_bytes": a.size_bytes, "sha256": a.sha256, "is_inline": a.is_inline,
             # M02 parse results - metadata only (no text) until the login exists
             "parse_status": a.parse_status, "parse_method": a.parse_method, "parse_reused": a.parse_reused,
             "parse_ms": a.parse_ms, "page_count": a.page_count, "chars": len(a.text_content or ""),
             "ocr_confidence": a.ocr_confidence, "language": a.language,
             "tables": len((a.layout or {}).get("tables", [])), "parse_error": a.parse_error}
            for a in atts
        ],
    }


@router.get("/emails", summary="E-mails received (newest first, metadata only)")
def list_emails(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0),
                sample_code: str | None = None, db: Session = Depends(get_db)):
    q = select(EmailMessage).order_by(EmailMessage.id.desc())
    if sample_code:
        q = q.where(EmailMessage.sample_code == sample_code)
    total = db.scalar(select(func.count()).select_from(q.order_by(None).subquery()))
    emails = db.scalars(q.limit(limit).offset(offset)).all()
    atts: dict[int, list[EmailAttachment]] = {}
    if emails:
        for a in db.scalars(select(EmailAttachment).where(EmailAttachment.email_id.in_([e.id for e in emails]))
                            .order_by(EmailAttachment.id)):
            atts.setdefault(a.email_id, []).append(a)
    cls: dict[int, EmailClassification] = {}
    if emails:
        cls = {c.email_id: c for c in db.scalars(select(EmailClassification).where(
            EmailClassification.email_id.in_([e.id for e in emails]), EmailClassification.is_current.is_(True)))}
    return {"total": total, "items": [_email_summary(e, atts.get(e.id, []), cls.get(e.id)) for e in emails]}


@admin.post("/gmail/poll", summary="Read new inbox e-mails now (one poll) - needs X-Admin-Key")
def poll_now(max_messages: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    try:
        r = poll(db, max_messages=max_messages)
    except GmailNotConfigured as exc:
        raise HTTPException(503, str(exc)) from exc
    except (PollAlreadyRunning, PollerDisabled) as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"fetched": r.fetched, "stored": r.stored, "already_stored": r.already_stored,
            "skipped_outbound": r.skipped_outbound, "ignored": r.ignored, "failed": r.failed,
            "email_refs": r.email_refs,
            "errors": r.errors}


@admin.post("/emails/{email_ref}/parse", summary="Read the body and attachments of one e-mail (M02) - needs X-Admin-Key")
def parse_now(email_ref: str, reparse: bool = False, db: Session = Depends(get_db)):
    from app.documents.service import parse_email

    email = db.scalar(select(EmailMessage).where(EmailMessage.email_ref == email_ref))
    if email is None:
        raise HTTPException(404, f"{email_ref} not found")
    s = parse_email(db, email, reparse=reparse)
    return {"email_ref": s.email_ref, "status": email.status, "parsed": s.parsed, "reused": s.reused,
            "skipped": s.skipped, "failed": s.failed, "reading_ms": s.ms, "saved_ms": s.saved_ms,
            "body_tables": s.body_tables, "errors": s.errors}


@admin.post("/emails/{email_ref}/classify",
            summary="Classify one e-mail as REMITTANCE / PTP / OUT_OF_SCOPE (M03) - needs X-Admin-Key")
def classify_now(email_ref: str, db: Session = Depends(get_db)):
    from app.classification.service import NotReadYet, classify_email, current_classification

    email = db.scalar(select(EmailMessage).where(EmailMessage.email_ref == email_ref))
    if email is None:
        raise HTTPException(404, f"{email_ref} not found")
    try:
        classify_email(db, email)
    except NotReadYet as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"email_ref": email.email_ref, "status": email.status,
            "classification": _classification_summary(current_classification(db, email.id))}
