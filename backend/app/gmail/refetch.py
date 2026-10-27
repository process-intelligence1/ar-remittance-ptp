"""Bring back Gmail messages that were labelled AR-Ignored under an older, wider ignore list.

find_no_longer_ignored()  messages with label AR-Ignored whose sender the CURRENT rule no longer ignores
release()                 removes the AR-Ignored label, so the next poll stores and processes them
"""
import base64
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import get_settings
from app.gmail import parsing
from app.gmail.client import ensure_label
from app.gmail.ignore import load_ignore_list


@dataclass
class IgnoredMessage:
    gmail_id: str
    sender: str | None
    original_sender: str | None
    subject: str | None
    still_ignored_by: str | None  # rule that still matches, or None = should be processed


def list_ignored(db: Session, service) -> list[IgnoredMessage]:
    s = get_settings()
    rules = load_ignore_list(db)
    out, page = [], None
    while True:
        resp = service.users().messages().list(userId="me", q=f'label:"{s.gmail_ignored_label}"',
                                               pageToken=page, maxResults=100).execute()
        for m in resp.get("messages", []):
            raw = base64.urlsafe_b64decode(
                service.users().messages().get(userId="me", id=m["id"], format="raw").execute()["raw"])
            p = parsing.parse_raw_email(raw)
            fwd = parsing.detect_forward(p.body_text)
            orig = fwd.sender_email if fwd.is_forwarded else None
            out.append(IgnoredMessage(m["id"], p.from_email, orig, p.subject, rules.match_any(p.from_email, orig)))
        page = resp.get("nextPageToken")
        if not page:
            return out


def release(service, gmail_ids: list[str]) -> int:
    """Remove AR-Ignored so the next poll (which skips that label) picks the messages up again."""
    ignored_id = ensure_label(service, get_settings().gmail_ignored_label)
    for gid in gmail_ids:
        service.users().messages().modify(userId="me", id=gid, body={"removeLabelIds": [ignored_id]}).execute()
    return len(gmail_ids)
