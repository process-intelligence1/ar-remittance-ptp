"""Gmail poller: inbox e-mails -> ar.email_message / ar.email_attachment (+ files in storage).

Rules
- Fetch inbox messages WITHOUT label AR-Processed; skip AR-Outbound and header X-AR-Demo: outbound.
- Store the raw .eml and every attachment (ZIPs unpacked recursively, children -> parent_id).
- Idempotent: gmail_id is unique; a message already in the database is only (re)labelled.
- After a successful database commit the message gets label AR-Processed.
"""
import base64
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.gmail import parsing
from app.gmail.client import build_service, ensure_label
from app.models.ar import AuditLog, EmailAttachment, EmailMessage, RuleConfig
from app.storage import Storage, get_storage, sha256_hex

log = logging.getLogger(__name__)

SAMPLE_HEADER = "x-ar-sample"     # set by the sample sender: the sample code, e.g. R01-0007
DEMO_HEADER = "x-ar-demo"         # "outbound" on e-mails the app sends itself (M09)


@dataclass
class PollResult:
    fetched: int = 0
    stored: int = 0
    already_stored: int = 0
    skipped_outbound: int = 0
    failed: int = 0
    email_refs: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- helpers
def current_business_date(db: Session) -> date:
    row = db.get(RuleConfig, "business_date")
    if row and isinstance(row.value, dict) and row.value.get("date"):
        return date.fromisoformat(row.value["date"])
    return get_settings().business_date


def next_email_ref(db: Session) -> str:
    n = db.execute(text("SELECT nextval('ar.email_ref_seq')")).scalar_one()
    return f"EML-{n:06d}"


def gmail_query() -> str:
    s = get_settings()
    q = f'in:inbox -label:"{s.gmail_processed_label}" -label:"{s.gmail_outbound_label}"'
    if s.gmail_ingest_since:
        q += f" after:{s.gmail_ingest_since.replace('-', '/')}"
    return q


# --------------------------------------------------------------------------- storing one e-mail
def store_email(db: Session, raw: bytes, *, storage: Storage | None = None, gmail_id: str | None = None,
                thread_id: str | None = None, internal_date_ms: int | None = None,
                source: str = "gmail") -> EmailMessage:
    """Parse and store one raw e-mail with its attachments. Caller commits."""
    storage = storage or get_storage()
    p = parsing.parse_raw_email(raw)
    fwd = parsing.detect_forward(p.body_text)
    sample_code = (p.headers.get(SAMPLE_HEADER) or "").strip() or None

    sender_name, sender_email = p.from_name, p.from_email
    if fwd.is_forwarded and fwd.sender_email:
        sender_name, sender_email = fwd.sender_name, fwd.sender_email

    received = p.date
    if received is None and internal_date_ms:
        received = datetime.fromtimestamp(internal_date_ms / 1000, tz=timezone.utc)

    ref = next_email_ref(db)
    folder = f"emails/{ref}"
    email = EmailMessage(
        email_ref=ref,
        source="sample" if sample_code and source == "gmail" else source,
        gmail_id=gmail_id,
        rfc_message_id=p.rfc_message_id,
        thread_id=thread_id,
        sample_code=sample_code,
        from_email=p.from_email,
        is_forwarded=fwd.is_forwarded,
        sender_email=sender_email,
        sender_name=sender_name,
        sender_domain=parsing.domain_of(sender_email),
        subject=p.subject,
        received_at=received,
        business_date=current_business_date(db),
        body_text=p.body_text,
        body_text_clean=parsing.clean_body(p.body_text, fwd),
        raw_uri=storage.put(f"{folder}/message.eml", raw, "message/rfc822"),
        sha256=sha256_hex(raw),
        status="NEW",
    )
    db.add(email)
    db.flush()

    errors: list[str] = []
    counter = 0

    def add_file(name: str, mime: str, data: bytes, *, path_prefix: str, parent: EmailAttachment | None,
                 depth: int, inline: bool = False) -> EmailAttachment:
        nonlocal counter
        counter += 1
        row = EmailAttachment(
            email_id=email.id,
            parent_id=parent.id if parent else None,
            filename=name,
            mime_type=mime,
            size_bytes=len(data),
            sha256=sha256_hex(data),
            storage_uri=storage.put(f"{path_prefix}/{counter:02d}_{name}", data, mime),
            is_inline=inline,
            depth=depth,
        )
        db.add(row)
        db.flush()
        return row

    def add_zip_children(entries: list[parsing.ZipEntry], parent: EmailAttachment, prefix: str) -> None:
        for e in entries:
            child = add_file(e.filename, e.mime_type, e.data, path_prefix=prefix, parent=parent, depth=e.depth)
            if e.children:
                add_zip_children(e.children, child, f"{prefix}/{counter:02d}_{e.filename}.d")

    for att in p.attachments:
        row = add_file(att.filename, att.mime_type, att.data, path_prefix=f"{folder}/att", parent=None,
                       depth=0, inline=att.is_inline)
        if parsing.is_zip(att.filename, att.data):
            try:
                add_zip_children(parsing.unpack_zip(att.data), row, f"{folder}/att/{counter:02d}_{att.filename}.d")
            except Exception as exc:  # bad/oversized ZIP: keep the ZIP itself, note the problem
                errors.append(f"{att.filename}: {exc}")

    if errors:
        email.error = "; ".join(errors)[:2000]
    db.add(AuditLog(
        business_date=email.business_date, actor="system", entity_type="email", entity_id=ref,
        action="EMAIL_INGESTED",
        details={"source": email.source, "gmail_id": gmail_id, "sample_code": sample_code,
                 "sender": sender_email, "forwarded": fwd.is_forwarded,
                 "attachments": counter, "errors": errors or None},
    ))
    return email


# --------------------------------------------------------------------------- the poll loop
POLL_LOCK_KEY = 7310001  # PostgreSQL advisory lock: only one poll at a time (API, scripts, worker)


class PollAlreadyRunning(RuntimeError):
    pass


def poll(db: Session, service=None, storage: Storage | None = None, max_messages: int | None = None) -> PollResult:
    """One poll, guarded so two polls never run at the same time. The lock is held on its own
    connection (an advisory lock belongs to a connection, and the session swaps connections)."""
    bind = db.get_bind()
    with getattr(bind, "engine", bind).connect() as lock_conn:  # bind is an Engine, or a Connection in tests
        if not lock_conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": POLL_LOCK_KEY}).scalar():
            raise PollAlreadyRunning("A Gmail poll is already running")
        try:
            return _poll(db, service, storage, max_messages)
        finally:
            lock_conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": POLL_LOCK_KEY})
            lock_conn.commit()


def _poll(db: Session, service, storage: Storage | None, max_messages: int | None) -> PollResult:
    s = get_settings()
    service = service or build_service()
    storage = storage or get_storage()
    processed_id = ensure_label(service, s.gmail_processed_label)
    outbound_id = ensure_label(service, s.gmail_outbound_label)
    limit = max_messages or s.gmail_max_per_poll
    result = PollResult()

    ids: list[str] = []
    page_token = None
    while len(ids) < limit:
        resp = service.users().messages().list(userId="me", q=gmail_query(), pageToken=page_token,
                                               maxResults=min(100, limit - len(ids))).execute()
        ids += [m["id"] for m in resp.get("messages", [])]
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    def label(gmail_id: str, label_id: str) -> None:
        service.users().messages().modify(userId="me", id=gmail_id, body={"addLabelIds": [label_id]}).execute()

    for gmail_id in ids[:limit]:
        result.fetched += 1
        try:
            if db.scalar(select(EmailMessage.id).where(EmailMessage.gmail_id == gmail_id)):
                result.already_stored += 1
                label(gmail_id, processed_id)
                continue
            msg = service.users().messages().get(userId="me", id=gmail_id, format="raw").execute()
            raw = base64.urlsafe_b64decode(msg["raw"].encode("ascii"))
            if outbound_id in msg.get("labelIds", []) or _is_outbound(raw):
                result.skipped_outbound += 1
                label(gmail_id, outbound_id)
                continue
            email = store_email(db, raw, storage=storage, gmail_id=gmail_id, thread_id=msg.get("threadId"),
                                internal_date_ms=int(msg.get("internalDate", 0)) or None)
            db.commit()
            result.stored += 1
            result.email_refs.append(email.email_ref)
            label(gmail_id, processed_id)
        except Exception as exc:  # one bad message must not stop the poll
            db.rollback()
            result.failed += 1
            result.errors.append(f"{gmail_id}: {type(exc).__name__}: {exc}")
            log.exception("Failed to ingest Gmail message %s", gmail_id)
    return result


def _is_outbound(raw: bytes) -> bool:
    head = raw.split(b"\r\n\r\n", 1)[0].split(b"\n\n", 1)[0].lower()
    return b"x-ar-demo: outbound" in head
