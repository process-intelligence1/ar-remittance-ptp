"""Read new inbox e-mails into the database once.

Run from the backend folder:
    python -m scripts.poll_gmail            # up to GMAIL_MAX_PER_POLL messages
    python -m scripts.poll_gmail --max 5
    python -m scripts.poll_gmail --force    # poll even where POLLER_ENABLED=false (the laptop)

The poller normally runs in Azure only. --force on the laptop takes new e-mails away from Azure
(the AR-Processed label hides them from the other side).
"""
import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.gmail.poller import PollerDisabled, poll
from app.models.ar import EmailAttachment, EmailMessage


def main(argv: list[str]) -> int:
    max_messages = int(argv[argv.index("--max") + 1]) if "--max" in argv else None
    force = "--force" in argv
    if force:
        print("WARNING: --force - this laptop now takes new inbox e-mails away from Azure.")
    with SessionLocal() as db:
        try:
            r = poll(db, max_messages=max_messages, force=force)
        except PollerDisabled as exc:
            print(f"{exc}\nUse --force to poll from here anyway.")
            return 1
        print(f"fetched {r.fetched} | stored {r.stored} | already stored {r.already_stored} | "
              f"skipped outbound {r.skipped_outbound} | ignored system senders {r.ignored} | failed {r.failed}")
        for ref in r.email_refs:
            e = db.scalar(select(EmailMessage).where(EmailMessage.email_ref == ref))
            atts = db.scalars(select(EmailAttachment).where(EmailAttachment.email_id == e.id)
                              .order_by(EmailAttachment.id)).all()
            fwd = " (forwarded)" if e.is_forwarded else ""
            print(f"  {ref}  {e.sample_code or '-':9}  {e.sender_email}{fwd}  '{e.subject}'")
            for a in atts:
                print(f"      {'  ' * a.depth}- {a.filename}  {a.size_bytes:,} bytes  sha256 {a.sha256[:12]}...")
        for err in r.errors:
            print(f"  ERROR {err}")
    return 1 if r.failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
