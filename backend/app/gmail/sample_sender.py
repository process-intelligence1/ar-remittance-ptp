"""Sample sender: put a sample e-mail from data/samples/emails/<CODE>/ into the Gmail inbox
with the CUSTOMER as sender (Gmail users.messages.import - nothing is sent over the internet
as mail, it is inserted straight into our own mailbox).

body.txt format:   From: ... / Subject: ... / Date: YYYY-MM-DD HH:MM:SS   (header lines)
                   <blank line>
                   body text
Every other file in the folder becomes an attachment.
"""
import io
import mimetypes
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from pathlib import Path

from app.config import PROJECT_ROOT, get_settings
from app.gmail.parsing import domain_of, split_address

LIVE_SET_FILE = PROJECT_ROOT / "data" / "samples" / "live_set.txt"  # chosen in M11


@dataclass
class Sample:
    code: str
    headers: dict[str, str]
    body: str
    attachments: list[Path]


def samples_root() -> Path:
    return Path(get_settings().samples_root)


def load_sample(code: str, root: Path | None = None) -> Sample:
    folder = (root or samples_root()) / code
    body_file = folder / "body.txt"
    if not body_file.exists():
        raise FileNotFoundError(f"Sample {code} not found ({body_file})")
    text = body_file.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    head, _, body = text.partition("\n\n")
    headers: dict[str, str] = {}
    for line in head.split("\n"):
        key, sep, value = line.partition(":")
        if sep and key.strip().lower() in ("from", "subject", "date", "to", "cc"):
            headers[key.strip().lower()] = value.strip()
    attachments = sorted(p for p in folder.iterdir() if p.is_file() and p.name != "body.txt")
    return Sample(code, headers, body.strip("\n") + "\n", attachments)


def _sample_date(value: str | None) -> datetime:
    """body.txt dates have no time zone: treated as UTC. Falls back to now."""
    if value:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                pass
    return datetime.now(timezone.utc)


def build_message(sample: Sample, to_address: str | None = None) -> EmailMessage:
    msg = EmailMessage()
    from_value = sample.headers.get("from", "")
    _, from_addr = split_address(from_value)
    msg["From"] = from_value
    msg["To"] = to_address or get_settings().gmail_address
    msg["Subject"] = sample.headers.get("subject", f"Sample {sample.code}")
    msg["Date"] = format_datetime(_sample_date(sample.headers.get("date")))
    msg["Message-ID"] = make_msgid(idstring=sample.code, domain=domain_of(from_addr) or "sample.local")
    msg["X-AR-Sample"] = sample.code
    msg.set_content(sample.body)
    for path in sample.attachments:
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        msg.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)
    return msg


def import_to_inbox(service, msg: EmailMessage) -> dict:
    """Insert into the inbox (INBOX + UNREAD) keeping From/Date as written. Returns the Gmail message."""
    from googleapiclient.http import MediaIoBaseUpload

    media = MediaIoBaseUpload(io.BytesIO(msg.as_bytes()), mimetype="message/rfc822", resumable=True)
    return service.users().messages().import_(
        userId="me",
        body={"labelIds": ["INBOX", "UNREAD"]},
        media_body=media,
        internalDateSource="dateHeader",
        neverMarkSpam=True,
        processForCalendar=False,
    ).execute()


def send_sample(service, code: str) -> dict:
    sample = load_sample(code)
    result = import_to_inbox(service, build_message(sample))
    return {"code": code, "gmail_id": result.get("id"), "from": sample.headers.get("from"),
            "subject": sample.headers.get("subject"), "attachments": [p.name for p in sample.attachments]}


def live_set() -> list[str]:
    if not LIVE_SET_FILE.exists():
        raise FileNotFoundError("No live set defined yet - it is chosen in module M11 (data/samples/live_set.txt).")
    return [c.strip() for c in LIVE_SET_FILE.read_text(encoding="utf-8").splitlines()
            if c.strip() and not c.startswith("#")]
