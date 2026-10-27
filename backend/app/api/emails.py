"""E-mails received (metadata only) and a manual Gmail poll.

Until the demo login exists (M08) these endpoints show NO e-mail bodies and NO files -
only references, senders, subjects, dates and attachment names/sizes/hashes.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.security import require_admin_key
from app.db import get_db
from app.gmail.client import GmailNotConfigured
from app.gmail.poller import PollAlreadyRunning, PollerDisabled, poll
from app.models.ar import EmailAttachment, EmailMessage

router = APIRouter(prefix="/api", tags=["E-mails"])
admin = APIRouter(prefix="/api/admin", tags=["Admin"], dependencies=[Depends(require_admin_key)])


def _email_summary(e: EmailMessage, atts: list[EmailAttachment]) -> dict:
    return {
        "email_ref": e.email_ref, "source": e.source, "sample_code": e.sample_code,
        "gmail_id": e.gmail_id, "sender_email": e.sender_email, "sender_name": e.sender_name,
        "from_email": e.from_email, "is_forwarded": e.is_forwarded, "sender_domain": e.sender_domain,
        "subject": e.subject, "received_at": e.received_at, "business_date": e.business_date,
        "status": e.status, "error": e.error, "created_at": e.created_at,
        "attachments": [
            {"id": a.id, "parent_id": a.parent_id, "depth": a.depth, "filename": a.filename,
             "mime_type": a.mime_type, "size_bytes": a.size_bytes, "sha256": a.sha256, "is_inline": a.is_inline}
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
    return {"total": total, "items": [_email_summary(e, atts.get(e.id, [])) for e in emails]}


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
