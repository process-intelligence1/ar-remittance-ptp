"""Classify stored e-mails (after reading them with scripts.parse_documents).

Run from the backend folder:
    python -m scripts.classify                      # read e-mails not classified yet (status PARSED)
    python -m scripts.classify --email EML-000037   # one e-mail (again)
    python -m scripts.classify --reclassify         # every read e-mail again (keeps the old results as history)
    python -m scripts.classify --gmail-labels       # also set the Gmail label (laptop; Azure always does)
"""
import sys
from collections import Counter

from sqlalchemy import select

from app.classification.service import CLASSIFIABLE, NotReadYet, classify_email
from app.db import SessionLocal
from app.models.ar import EmailMessage


def main(argv: list[str]) -> int:
    service = None
    if "--gmail-labels" in argv:
        from app.gmail.client import build_service
        service = build_service()
    with SessionLocal() as db:
        q = select(EmailMessage).order_by(EmailMessage.id)
        if "--email" in argv:
            q = q.where(EmailMessage.email_ref == argv[argv.index("--email") + 1])
        elif "--reclassify" in argv:
            q = q.where(EmailMessage.status.in_(CLASSIFIABLE))
        else:
            q = q.where(EmailMessage.status == "PARSED")
        emails = db.scalars(q).all()
        totals, failed = Counter(), 0
        for e in emails:
            try:
                r = classify_email(db, e, gmail_service=service)
            except NotReadYet as exc:
                print(f"{e.email_ref}: skipped - {exc}")
                failed += 1
                continue
            totals[r.key] += 1
            flags = "+".join(f for f, on in (("remittance", r.contains_remittance), ("ptp", r.contains_ptp)) if on)
            signals = ", ".join(h["signal"] for h in r.reasons.get("signals", [])[:4]) or "-"
            print(f"{e.email_ref} {e.sample_code or '':<10} {r.label:<12} {r.out_of_scope_category or flags:<17} "
                  f"{r.confidence:>5.1f}% {r.method:<11} | {(e.subject or '')[:45]:<45} | {signals}")
        print(f"\n{len(emails)} e-mail(s): {dict(totals)}" + (f", {failed} not read yet" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
