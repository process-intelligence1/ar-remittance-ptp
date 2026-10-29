"""The worker: polls Gmail, then processes queued e-mails.

    python -m app.worker --once                 # one round: run this from any scheduler (cron, a cloud job, Task Scheduler)
    python -m app.worker --loop --interval 60   # keep going (laptop)
    python -m app.worker --once --force-poll    # poll Gmail from here even though POLLER_ENABLED=false

One round: (1) poll Gmail (only where POLLER_ENABLED is true), (2) queue a PROCESS_EMAIL job for every e-mail
that is not finished and has none, (3) work through due jobs until none is left or the time budget is used,
(4) PTP checks (placeholder until M10). Several workers may run at once: jobs are claimed with SKIP LOCKED.
"""
import argparse
import logging
import sys
import time
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import jobs
from app.config import get_settings
from app.db import SessionLocal
from app.models.ar import EmailMessage
from app.pipeline import IN_FLIGHT, PipelineError, process_email

log = logging.getLogger("worker")


@dataclass
class RoundSummary:
    polled: str = "skipped"
    stored: int = 0
    queued: int = 0
    released: int = 0
    done: int = 0
    retried: int = 0
    failed: int = 0
    unfinished: int = 0  # due jobs left because the time budget ran out
    errors: list[str] = field(default_factory=list)

    def line(self) -> str:
        return (f"poll {self.polled} (stored {self.stored}) | queued {self.queued} | done {self.done} | "
                f"retry scheduled {self.retried} | failed {self.failed} | released {self.released} | "
                f"left for next round {self.unfinished}")


def poll_gmail(db: Session, force: bool, summary: RoundSummary) -> None:
    from app.gmail.client import GmailNotConfigured
    from app.gmail.poller import PollAlreadyRunning, PollerDisabled, poll

    if not (get_settings().poller_enabled or force):
        summary.polled = "off here"
        return
    try:
        r = poll(db, force=force)
        summary.polled, summary.stored = f"ok ({r.fetched} seen)", r.stored
        summary.errors += r.errors
    except PollAlreadyRunning:
        summary.polled = "already running"
    except (PollerDisabled, GmailNotConfigured) as exc:
        summary.polled = "not possible"
        summary.errors.append(str(exc))
    except Exception as exc:  # a Gmail outage must not stop the processing of what is already stored
        db.rollback()
        summary.polled = "failed"
        summary.errors.append(f"poll: {type(exc).__name__}: {exc}")
        log.exception("Gmail poll failed")


def queue_unfinished(db: Session) -> int:
    """Every e-mail that is mid-way and has no active job gets one (covers new mail and a crashed worker)."""
    n = 0
    for ref in db.scalars(select(EmailMessage.email_ref).where(EmailMessage.status.in_(IN_FLIGHT))
                          .order_by(EmailMessage.received_at.nulls_first(), EmailMessage.id)):
        if jobs.active_job_for_email(db, ref) is None:
            jobs.enqueue(db, jobs.PROCESS_EMAIL, {"email_ref": ref})
            n += 1
    db.commit()
    return n


def ptp_checks(db: Session) -> int:
    """Daily promise-to-pay checks arrive with M10."""
    return 0


def work_jobs(db: Session, summary: RoundSummary, budget_s: float) -> None:
    deadline = time.monotonic() + budget_s
    while time.monotonic() < deadline:
        job = jobs.claim_next(db, jobs.PROCESS_EMAIL)
        if job is None:
            return
        ref = (job.payload or {}).get("email_ref")
        try:
            email = db.scalar(select(EmailMessage).where(EmailMessage.email_ref == ref))
            if email is None:
                raise LookupError(f"e-mail {ref} not found")
            process_email(db, email, last_attempt=job.attempts >= job.max_attempts)
            jobs.complete(db, job)
            summary.done += 1
        except Exception as exc:
            db.rollback()
            message = str(exc) if isinstance(exc, PipelineError) else f"{type(exc).__name__}: {exc}"
            new_status = jobs.fail(db, job, message)
            summary.retried += new_status == "QUEUED"
            summary.failed += new_status == "FAILED"
            log.warning("Job %s for %s: attempt %s/%s failed (%s) -> %s", job.id, ref, job.attempts,
                        job.max_attempts, message, new_status)
    db_due = db.scalars(select(jobs.Job.id).where(jobs.Job.status == "QUEUED", jobs.Job.run_after <= jobs._now())).all()
    summary.unfinished = len(db_due)


def run_once(db: Session, *, force_poll: bool = False, budget_s: float | None = None) -> RoundSummary:
    summary = RoundSummary()
    poll_gmail(db, force_poll, summary)
    summary.released = jobs.release_stuck(db)
    summary.queued = queue_unfinished(db)
    work_jobs(db, summary, get_settings().worker_time_budget_s if budget_s is None else budget_s)
    ptp_checks(db)
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--loop", action="store_true")
    ap.add_argument("--interval", type=int, default=60, help="seconds between rounds with --loop")
    ap.add_argument("--force-poll", action="store_true", help="poll Gmail even where POLLER_ENABLED=false")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    if args.force_poll:
        print("WARNING: --force-poll - this laptop now takes new inbox e-mails away from the hosted worker.")
    while True:
        with SessionLocal() as db:
            s = run_once(db, force_poll=args.force_poll)
        print(s.line())
        for e in s.errors:
            print(f"  ERROR {e}")
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
