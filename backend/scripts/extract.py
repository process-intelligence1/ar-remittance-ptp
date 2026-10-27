"""Extract header + invoice lines from stored e-mails (after reading and classification).

Run from the backend folder:
    python -m scripts.extract                      # classified e-mails not extracted yet
    python -m scripts.extract --email EML-000037   # one e-mail (again)
    python -m scripts.extract --reextract          # every classified e-mail again (old runs kept as history)
    python -m scripts.extract --reclean            # first re-compute body_text_clean with the current
                                                   # reply-history rules (M04 fix), then extract
"""
import sys
from collections import Counter

from sqlalchemy import select

from app.db import SessionLocal
from app.extraction.service import EXTRACTABLE, NotClassifiedYet, extract_email
from app.gmail.parsing import clean_body
from app.models.ar import EmailMessage


def main(argv: list[str]) -> int:
    with SessionLocal() as db:
        q = select(EmailMessage).order_by(EmailMessage.id)
        if "--email" in argv:
            q = q.where(EmailMessage.email_ref == argv[argv.index("--email") + 1])
        elif "--reextract" in argv or "--reclean" in argv:
            q = q.where(EmailMessage.status.in_(EXTRACTABLE))
        else:
            q = q.where(EmailMessage.status == "CLASSIFIED")
        emails = db.scalars(q).all()
        totals, skipped = Counter(), 0
        for e in emails:
            if "--reclean" in argv and e.body_text:
                e.body_text_clean = clean_body(e.body_text)
            try:
                r = extract_email(db, e)
            except NotClassifiedYet as exc:
                print(f"{e.email_ref}: skipped - {exc}")
                skipped += 1
                continue
            totals[r.status] += 1
            h = r.header
            refs = ", ".join(f"{l.ref_raw}={l.amount if l.amount is not None else '?'}" for l in r.lines[:4])
            print(f"{e.email_ref} {e.sample_code or '':<10} {r.status:<8} {len(r.lines):>2} line(s) "
                  f"total={h.total} {h.payment_currency or ''} ref={h.payment_reference or h.advice_number or '-'} "
                  f"| {refs}{' ...' if len(r.lines) > 4 else ''}" + (f"  WARN: {'; '.join(r.warnings)}" if r.warnings else ""))
        print(f"\n{len(emails)} e-mail(s): {dict(totals)}" + (f", {skipped} not classified yet" if skipped else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
