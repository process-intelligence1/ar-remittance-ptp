"""Match extracted e-mails to BSID: one ar.work_item per invoice, scored and decided (M05).

Run from the backend folder:
    python -m scripts.match                      # extracted e-mails not matched yet
    python -m scripts.match --email EML-000037   # one e-mail (again)
    python -m scripts.match --rematch            # all extracted / processed e-mails again
                                                 # (rows an analyst has acted on are never replaced)
"""
import sys
from collections import Counter

from sqlalchemy import select

from app.db import SessionLocal
from app.matching.data import load_sap
from app.matching.service import MATCHABLE, AlreadyWorkedOn, NotExtractedYet, match_stored_email
from app.models.ar import EmailMessage


def main(argv: list[str]) -> int:
    with SessionLocal() as db:
        q = select(EmailMessage).order_by(EmailMessage.received_at.nulls_first(), EmailMessage.id)
        if "--email" in argv:
            q = q.where(EmailMessage.email_ref == argv[argv.index("--email") + 1])
        elif "--rematch" in argv:
            q = q.where(EmailMessage.status.in_(MATCHABLE))
        else:
            q = q.where(EmailMessage.status == "EXTRACTED")
        emails = db.scalars(q).all()
        sap = load_sap(db)
        decisions, skipped = Counter(), 0
        for e in emails:
            try:
                rows = match_stored_email(db, e, sap)
            except (NotExtractedYet, AlreadyWorkedOn) as exc:
                print(f"{e.email_ref}: skipped - {exc}")
                skipped += 1
                db.rollback()
                continue
            for w in rows:
                decisions[w.decision] += 1
                print(f"{e.email_ref} {w.entry_id} {w.final_classification:<12} {w.invoice_ref_raw or '-':<16} "
                      f"cust={(w.kunnr or '-').lstrip('0'):<7} {w.amount if w.amount is not None else '-'} {w.currency or ''} "
                      f"{w.match_level or w.match_type or '-':<18} {w.confidence_score}% ({w.confidence_source}) "
                      f"{w.decision}" + (f"  [{'; '.join(w.review_reasons)}]" if w.review_reasons else "")
                      + (f"  [{w.exception_reason}]" if w.exception_reason else ""))
        print(f"\n{len(emails)} e-mail(s), decisions: {dict(decisions)}" + (f", {skipped} skipped" if skipped else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
