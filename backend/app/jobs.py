"""Job queue kept in PostgreSQL (table ar.job): no Redis, no Celery.

A job is QUEUED -> RUNNING -> DONE. When it fails it goes back to QUEUED with a delay
(RETRY_DELAYS_S), until max_attempts (3) is used up; then it is FAILED and stays visible.
Workers claim jobs with FOR UPDATE SKIP LOCKED, so two workers never take the same job.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ar import Job

PROCESS_EMAIL = "PROCESS_EMAIL"
RETRY_DELAYS_S = (60, 300)        # wait before attempt 2, before attempt 3
STUCK_AFTER = timedelta(minutes=15)  # a RUNNING job this old belongs to a crashed worker
ACTIVE = ("QUEUED", "RUNNING")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enqueue(db: Session, job_type: str, payload: dict | None = None, *, run_after: datetime | None = None,
            max_attempts: int = 3) -> Job:
    """Queue a job. For PROCESS_EMAIL an e-mail has at most one active job (the existing one is returned)."""
    if job_type == PROCESS_EMAIL and payload:
        existing = active_job_for_email(db, payload["email_ref"])
        if existing:
            return existing
    job = Job(job_type=job_type, payload=payload, max_attempts=max_attempts, run_after=run_after or _now())
    db.add(job)
    db.flush()
    return job


def active_job_for_email(db: Session, email_ref: str) -> Job | None:
    return db.scalar(select(Job).where(Job.job_type == PROCESS_EMAIL, Job.status.in_(ACTIVE),
                                       Job.payload["email_ref"].astext == email_ref).limit(1))


def claim_next(db: Session, job_type: str | None = None) -> Job | None:
    """Take the next due job (oldest first) and mark it RUNNING; commits so other workers see it."""
    q = select(Job).where(Job.status == "QUEUED", Job.run_after <= _now()).order_by(Job.run_after, Job.id) \
        .limit(1).with_for_update(skip_locked=True)
    if job_type:
        q = q.where(Job.job_type == job_type)
    job = db.scalar(q)
    if job is None:
        db.rollback()
        return None
    job.status, job.attempts, job.started_at, job.finished_at = "RUNNING", job.attempts + 1, _now(), None
    db.commit()
    return job


def complete(db: Session, job: Job) -> None:
    job.status, job.finished_at, job.last_error = "DONE", _now(), None
    db.commit()


def fail(db: Session, job: Job, error: str) -> str:
    """Record a failed attempt. Returns the job's new status (QUEUED = will be retried, FAILED = gave up)."""
    job.last_error = error[:2000]
    if job.attempts >= job.max_attempts:
        job.status, job.finished_at = "FAILED", _now()
    else:
        delay = RETRY_DELAYS_S[min(job.attempts - 1, len(RETRY_DELAYS_S) - 1)]
        job.status, job.run_after = "QUEUED", _now() + timedelta(seconds=delay)
    db.commit()
    return job.status


def release_stuck(db: Session) -> int:
    """Jobs left RUNNING by a worker that died: retry them (or fail them when the attempts are used up)."""
    stuck = db.scalars(select(Job).where(Job.status == "RUNNING", Job.started_at < _now() - STUCK_AFTER)
                       .with_for_update(skip_locked=True)).all()
    for j in stuck:
        j.last_error = "worker stopped before finishing this job"
        j.status = "FAILED" if j.attempts >= j.max_attempts else "QUEUED"
        j.finished_at = _now() if j.status == "FAILED" else None
        j.run_after = _now()
    db.commit()
    return len(stuck)


def requeue_failed(db: Session, email_ref: str | None = None) -> int:
    """Give FAILED PROCESS_EMAIL jobs a fresh set of attempts (the 're-process' button / admin call)."""
    q = select(Job).where(Job.job_type == PROCESS_EMAIL, Job.status == "FAILED")
    if email_ref:
        q = q.where(Job.payload["email_ref"].astext == email_ref)
    jobs = db.scalars(q).all()
    for j in jobs:
        j.status, j.attempts, j.run_after, j.finished_at = "QUEUED", 0, _now(), None
    db.commit()
    return len(jobs)
