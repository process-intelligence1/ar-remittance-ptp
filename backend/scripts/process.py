"""Process e-mails through the whole pipeline (read -> classify -> extract -> match) on this computer.

Run from the backend folder:
    python -m scripts.process                    # every unfinished e-mail (jobs, with retries)
    python -m scripts.process --email EML-000037 # one e-mail, straight through (errors are shown)
    python -m scripts.process --jobs             # list queued / failed jobs
"""
import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.models.ar import EmailMessage, Job
from app.pipeline import PipelineError, process_email
from app.worker import run_once


def main(argv: list[str]) -> int:
    with SessionLocal() as db:
        if "--jobs" in argv:
            for j in db.scalars(select(Job).where(Job.status != "DONE").order_by(Job.id)):
                print(f"job {j.id} {j.status:<8} {(j.payload or {}).get('email_ref')} "
                      f"attempt {j.attempts}/{j.max_attempts} {j.last_error or ''}")
            return 0
        if "--email" in argv:
            ref = argv[argv.index("--email") + 1]
            e = db.scalar(select(EmailMessage).where(EmailMessage.email_ref == ref))
            if e is None:
                print(f"{ref} not found")
                return 1
            try:
                r = process_email(db, e)
            except PipelineError as exc:
                print(f"{ref} FAILED at {exc}")
                return 1
            print(f"{ref}: stages {r.stages_run}, {r.work_items} work item(s), status {e.status}")
            return 0
        s = run_once(db, budget_s=3600)
        print(s.line())
        for err in s.errors:
            print(f"  ERROR {err}")
        failed = db.scalars(select(Job).where(Job.status == "QUEUED", Job.attempts > 0)).all()
        for j in failed:
            print(f"  waiting for retry: {(j.payload or {}).get('email_ref')} - {j.last_error}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
