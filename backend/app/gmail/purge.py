"""Remove already-stored e-mails whose sender is now on the ignore list ("ignored_senders").

find_ignored_emails()  -> what would be deleted (for review first)
purge_emails()         -> deletes files (raw .eml + attachments) and database rows, writes one
                          audit entry per e-mail (date, sender, reason; no content) and moves the
                          Gmail message from label AR-Processed to AR-Ignored.
"""
import logging
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.gmail.client import ensure_label
from app.gmail.ignore import REASON, SenderIgnoreList, load_ignore_list
from app.gmail.poller import current_business_date
from app.models.ar import AuditLog, EmailAttachment, EmailMessage
from app.storage import Storage, get_storage

log = logging.getLogger(__name__)


@dataclass
class PurgeCandidate:
    email: EmailMessage
    rule: str
    attachments: int


def find_ignored_emails(db: Session, ignore_list: SenderIgnoreList | None = None) -> list[PurgeCandidate]:
    ignore_list = ignore_list or load_ignore_list(db)
    found = []
    for e in db.scalars(select(EmailMessage).order_by(EmailMessage.id)):
        rule = ignore_list.match_any(e.from_email, e.sender_email)
        if rule:
            n = len(db.scalars(select(EmailAttachment.id).where(EmailAttachment.email_id == e.id)).all())
            found.append(PurgeCandidate(e, rule, n))
    return found


def purge_emails(db: Session, candidates: list[PurgeCandidate], storage: Storage | None = None,
                 service=None) -> dict:
    """Delete the candidates. Files first, then rows; one transaction for the database part."""
    storage = storage or get_storage()
    s = get_settings()
    business_date = current_business_date(db)
    files = rows = 0
    relabel: list[str] = []
    for c in candidates:
        e = c.email
        uris = [a.storage_uri for a in db.scalars(select(EmailAttachment).where(EmailAttachment.email_id == e.id))
                if a.storage_uri]
        for uri in uris + ([e.raw_uri] if e.raw_uri else []):
            storage.delete(uri)
            files += 1
        db.add(AuditLog(
            business_date=business_date, actor="system", entity_type="email", entity_id=e.email_ref,
            action="EMAIL_PURGED_IGNORED_SENDER",
            details={"date": e.received_at.isoformat() if e.received_at else None, "sender": e.from_email,
                     "reason": REASON, "rule": c.rule, "gmail_id": e.gmail_id},
        ))
        if e.gmail_id:
            relabel.append(e.gmail_id)
        db.execute(delete(EmailMessage).where(EmailMessage.id == e.id))  # attachments go with it (ON DELETE CASCADE)
        rows += 1
    db.commit()

    relabelled = 0
    if service is not None and relabel:
        processed_id = ensure_label(service, s.gmail_processed_label)
        ignored_id = ensure_label(service, s.gmail_ignored_label)
        for gid in relabel:
            try:
                service.users().messages().modify(
                    userId="me", id=gid, body={"addLabelIds": [ignored_id], "removeLabelIds": [processed_id]}
                ).execute()
                relabelled += 1
            except Exception:  # message may have been deleted in Gmail meanwhile; data is already purged
                log.warning("Could not relabel Gmail message %s", gid, exc_info=True)
    return {"emails_deleted": rows, "files_deleted": files, "gmail_relabelled": relabelled}
