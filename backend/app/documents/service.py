"""Parse stored e-mails: body + every attachment, results saved on the database rows.

Reuse: if a file with the same SHA-256 was parsed before, its result is copied (parse_reused =
true, parse_ms = the time the original took = time saved) instead of reading it again.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.documents.body import parse_body
from app.documents.common import DocumentTimeout
from app.documents.router import timed_parse
from app.gmail.parsing import parse_raw_email
from app.gmail.poller import current_business_date
from app.models.ar import AuditLog, EmailAttachment, EmailMessage
from app.storage import Storage, get_storage

log = logging.getLogger(__name__)
COPY_FIELDS = ("text_content", "layout", "parse_method", "ocr_confidence", "language", "page_count")


@dataclass
class EmailParseSummary:
    email_ref: str
    parsed: int = 0
    reused: int = 0
    skipped: int = 0
    failed: int = 0
    ms: int = 0
    saved_ms: int = 0
    body_tables: int = 0
    errors: list[str] = field(default_factory=list)


def find_reusable(db: Session, att: EmailAttachment) -> EmailAttachment | None:
    if not att.sha256:
        return None
    return db.scalar(select(EmailAttachment)
                     .where(EmailAttachment.sha256 == att.sha256, EmailAttachment.id != att.id,
                            EmailAttachment.parse_status == "PARSED")
                     .order_by(EmailAttachment.parse_reused, EmailAttachment.id).limit(1))


def parse_attachment(db: Session, att: EmailAttachment, storage: Storage | None = None,
                     timeout_s: float | None = None) -> str:
    """Parse (or reuse) one attachment. Returns its new parse_status."""
    now = datetime.now(timezone.utc)
    source = find_reusable(db, att)
    if source is not None:
        for f in COPY_FIELDS:
            setattr(att, f, getattr(source, f))
        att.parse_status, att.parse_error, att.parse_reused = "PARSED", None, True
        att.parse_ms, att.parsed_at = source.parse_ms, now
        return att.parse_status
    storage = storage or get_storage()
    try:
        data = storage.get(att.storage_uri)
        r, ms = timed_parse(att.filename, att.mime_type, data, timeout_s)
        del data
        att.text_content, att.layout = r.text or None, r.layout if r.status == "PARSED" else None
        att.parse_method, att.ocr_confidence, att.language, att.page_count = r.method, r.ocr_confidence, r.language, r.page_count
        att.parse_status, att.parse_error, att.parse_ms = r.status, r.note, ms
    except DocumentTimeout as exc:
        att.parse_status, att.parse_error = "FAILED", f"timeout ({exc})"
    except Exception as exc:  # a broken file must not stop the others
        log.exception("Parsing %s failed", att.filename)
        att.parse_status, att.parse_error = "FAILED", f"{type(exc).__name__}: {exc}"[:2000]
    att.parse_reused, att.parsed_at = False, now
    return att.parse_status


def parse_email(db: Session, email: EmailMessage, storage: Storage | None = None, reparse: bool = False,
                timeout_s: float | None = None) -> EmailParseSummary:
    """Body + attachments of one e-mail; commits once at the end."""
    storage = storage or get_storage()
    summary = EmailParseSummary(email.email_ref)

    # --- body (HTML tables need the original HTML part from the stored .eml)
    html = None
    if email.raw_uri:
        try:
            html = parse_raw_email(storage.get(email.raw_uri)).body_html
        except Exception:
            log.warning("Could not re-read %s for its HTML body", email.raw_uri, exc_info=True)
    email.body_layout, email.language = parse_body(email.body_text_clean or email.body_text or "", html)
    summary.body_tables = len(email.body_layout["tables"])

    # --- attachments, one at a time, in the order they were stored
    atts = db.scalars(select(EmailAttachment).where(EmailAttachment.email_id == email.id)
                      .order_by(EmailAttachment.id)).all()
    for att in atts:
        if att.parse_status in ("PARSED", "SKIPPED") and not reparse:
            continue
        if reparse:
            att.parse_status = "PENDING"
        status = parse_attachment(db, att, storage, timeout_s)
        db.flush()
        if att.parse_reused:
            summary.reused += 1
            summary.saved_ms += att.parse_ms or 0
        elif status == "PARSED":
            summary.parsed += 1
            summary.ms += att.parse_ms or 0
        elif status == "SKIPPED":
            summary.skipped += 1
        else:
            summary.failed += 1
            summary.errors.append(f"{att.filename}: {att.parse_error}")

    email.status = "FAILED" if summary.failed else "PARSED"
    email.error = "; ".join(summary.errors)[:2000] if summary.errors else None
    db.add(AuditLog(business_date=current_business_date(db), actor="system", entity_type="email",
                    entity_id=email.email_ref, action="EMAIL_PARSED",
                    details={"parsed": summary.parsed, "reused": summary.reused, "skipped": summary.skipped,
                             "failed": summary.failed, "ms": summary.ms, "saved_ms": summary.saved_ms,
                             "body_tables": summary.body_tables, "errors": summary.errors or None}))
    db.commit()
    return summary
