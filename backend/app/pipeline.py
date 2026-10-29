"""The processing pipeline: one e-mail -> read (M02) -> classify (M03) -> extract (M04) -> match (M05).

Each stage is idempotent and the next stage is chosen from what is already stored (not only from the
e-mail status), so a retry carries on at the stage that failed instead of starting over.
Every finished or failed stage writes an ar.audit_log entry (actor "system", entity e-mail).
A failure raises PipelineError after rolling back, recording the error on the e-mail
(status FAILED, error "<STAGE>: ...") - the job queue (app/jobs.py) decides about retries.
"""
import logging
import time
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.classification.service import classify_email, current_classification
from app.documents.service import parse_email
from app.extraction.service import current_extraction, extract_email
from app.gmail.poller import current_business_date
from app.matching.matcher import _business_days
from app.matching.service import AlreadyWorkedOn, all_rules, match_stored_email
from app.models.ar import AuditLog, EmailMessage, WorkItem

log = logging.getLogger(__name__)

PARSE, CLASSIFY, EXTRACT, MATCH = "PARSE", "CLASSIFY", "EXTRACT", "MATCH"
STAGES = (PARSE, CLASSIFY, EXTRACT, MATCH)
# the e-mail status each stage expects to find (a FAILED e-mail is put back to this before the stage runs)
STATUS_BEFORE = {PARSE: "NEW", CLASSIFY: "PARSED", EXTRACT: "CLASSIFIED", MATCH: "EXTRACTED"}
UNREADABLE = "ATTACHMENT_UNREADABLE"  # email.error prefix: processed without one or more unreadable attachments
UNREADABLE_REASON = "Attachment unreadable"
IN_FLIGHT = ("NEW", "PARSED", "CLASSIFIED", "EXTRACTED")  # statuses the worker still has to move forward


class PipelineError(Exception):
    def __init__(self, stage: str, message: str):
        super().__init__(f"{stage}: {message}")
        self.stage = stage


@dataclass
class PipelineResult:
    email_ref: str
    stages_run: list[str] = field(default_factory=list)
    ms: dict[str, int] = field(default_factory=dict)
    work_items: int = 0
    note: str | None = None


def next_stage(db: Session, email: EmailMessage) -> str | None:
    """The first stage whose result is missing; None when the e-mail is completely processed."""
    if email.status == "PROCESSED":
        return None
    if email.body_layout is None or email.status == "NEW" or (email.error or "").startswith(f"{PARSE}:"):
        return PARSE
    if current_classification(db, email.id) is None:
        return CLASSIFY
    if current_extraction(db, email.id) is None:
        return EXTRACT
    return MATCH


def _audit(db: Session, email: EmailMessage, action: str, details: dict) -> None:
    db.add(AuditLog(business_date=current_business_date(db), actor="system", entity_type="email",
                    entity_id=email.email_ref, action=action, details=details))


def _run(db: Session, email: EmailMessage, stage: str, storage=None, last_attempt: bool = False) -> dict:
    if stage == PARSE:
        s = parse_email(db, email, storage=storage)
        if s.failed:  # M02 marks the e-mail FAILED and keeps the reasons in email.error
            problem = f"{s.failed} attachment(s) could not be read: {'; '.join(s.errors)[:500]}"
            if not last_attempt:
                raise RuntimeError(problem)
            # last attempt: carry on with the body and the readable attachments; the rows go to review
            email.status, email.error = "PARSED", f"{UNREADABLE}: {problem}"[:2000]
            return {"parsed": s.parsed, "reused": s.reused, "skipped": s.skipped, "unreadable": s.errors}
        return {"parsed": s.parsed, "reused": s.reused, "skipped": s.skipped}
    if stage == CLASSIFY:
        r = classify_email(db, email)
        return {"label": r.label, "method": r.method}
    if stage == EXTRACT:
        r = extract_email(db, email)
        return {"lines": len(r.lines), "warnings": len(r.warnings or [])}
    try:
        rows = match_stored_email(db, email)
    except AlreadyWorkedOn as exc:  # an analyst already acted: leave the rows alone, nothing to retry
        return {"rows": 0, "note": str(exc)}
    if (email.error or "").startswith(UNREADABLE):
        _route_to_review(db, email, rows)
    return {"rows": len(rows)}


def _route_to_review(db: Session, email: EmailMessage, rows: list[WorkItem]) -> None:
    """Rows built without an unreadable attachment are never auto-processed: they need a person."""
    sla_days = int(all_rules(db)["sla"]["pending_review_business_days"])
    changed = []
    for w in rows:
        if w.decision in ("DUPLICATE", "OUT_OF_SCOPE"):
            continue
        w.review_reasons = [*(w.review_reasons or []), UNREADABLE_REASON]
        if w.decision == "AUTO_PROCESS":
            w.decision, w.status = "MANUAL_REVIEW", "PENDING_REVIEW"
            w.recommended_action = "Add / Update Invoice Details"
            w.sla_due_at = _business_days(current_business_date(db), sla_days)
        changed.append(w.entry_id)
    _audit(db, email, "ATTACHMENT_UNREADABLE_REVIEW", {"rows": changed, "problem": email.error})


def process_email(db: Session, email: EmailMessage, storage=None, last_attempt: bool = False) -> PipelineResult:
    """Run every missing stage. Raises PipelineError at the first failing stage.
    last_attempt: an unreadable attachment no longer fails the e-mail; its rows go to review instead."""
    result = PipelineResult(email.email_ref)
    while (stage := next_stage(db, email)) is not None:
        if stage in result.stages_run:  # a stage that did not move the e-mail on would loop forever
            raise PipelineError(stage, "stage finished but the e-mail did not advance")
        if email.status == "FAILED":
            email.status = STATUS_BEFORE[stage]
        started = time.monotonic()
        try:
            detail = _run(db, email, stage, storage, last_attempt)
        except Exception as exc:
            db.rollback()
            ms = int((time.monotonic() - started) * 1000)
            message = f"{type(exc).__name__}: {exc}"[:1500]
            email = db.get(EmailMessage, email.id)
            email.status, email.error = "FAILED", f"{stage}: {message}"
            _audit(db, email, "PIPELINE_STAGE_FAILED", {"stage": stage, "error": message, "ms": ms})
            db.commit()
            log.warning("Pipeline %s failed at %s: %s", email.email_ref, stage, message)
            raise PipelineError(stage, message) from exc
        ms = int((time.monotonic() - started) * 1000)
        result.stages_run.append(stage)
        result.ms[stage] = ms
        if detail.get("note"):
            result.note = detail["note"]
        if stage == MATCH:
            result.work_items = detail.get("rows", 0)
        _audit(db, email, "PIPELINE_STAGE_DONE", {"stage": stage, "ms": ms, **detail})
        db.commit()
        if stage == MATCH:
            break
    if email.error and email.status == "PROCESSED" and not email.error.startswith(UNREADABLE):
        email.error = None  # an earlier failure was overcome by a retry
        db.commit()
    return result

