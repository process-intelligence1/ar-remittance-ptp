"""Remove stored e-mails from ignored system senders (rule "ignored_senders").

Run from the backend folder:
    python -m scripts.purge_ignored          # LIST only - nothing is deleted
    python -m scripts.purge_ignored --yes    # delete rows + files, relabel in Gmail as AR-Ignored
"""
import sys

from app.db import SessionLocal
from app.gmail.client import GmailNotConfigured, build_service
from app.gmail.purge import find_ignored_emails, purge_emails


def main(argv: list[str]) -> int:
    with SessionLocal() as db:
        found = find_ignored_emails(db)
        print(f"{len(found)} stored e-mail(s) from ignored senders:")
        for c in found:
            e = c.email
            when = e.received_at.strftime("%Y-%m-%d %H:%M") if e.received_at else "-"
            print(f"  {e.email_ref}  {when}  {e.from_email:45}  [{c.rule}]  {c.attachments} attachment(s)"
                  f"  '{(e.subject or '')[:60]}'")
        if "--yes" not in argv:
            print("\nNothing deleted (list only). Run again with --yes to delete.")
            return 0
        if not found:
            return 0
        try:
            service = build_service()
        except GmailNotConfigured:
            service = None
            print("Gmail not configured: data will be deleted, labels left unchanged.")
        r = purge_emails(db, found, service=service)
        print(f"\nDeleted {r['emails_deleted']} e-mail(s) and {r['files_deleted']} file(s); "
              f"relabelled {r['gmail_relabelled']} in Gmail (AR-Processed -> AR-Ignored).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
