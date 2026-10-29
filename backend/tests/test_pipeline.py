"""M06: pipeline stages, job queue (retries), worker round and the "Process now" endpoint."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import azure_jobs, jobs, pipeline, worker
from app.config import get_settings
from app.db import get_db
from app.gmail.poller import store_email
from app.gmail.sample_sender import build_message, load_sample
from app.main import app
from app.models.ar import AuditLog, EmailMessage, WorkItem
from app.pipeline import PipelineError, process_email


def _stored(db, storage, code: str, gmail_id: str) -> EmailMessage:
    e = store_email(db, build_message(load_sample(code)).as_bytes(), storage=storage, gmail_id=gmail_id)
    db.commit()
    return e


def _audit(db, e, action):
    return db.scalars(select(AuditLog).where(AuditLog.entity_id == e.email_ref, AuditLog.action == action)
                      .order_by(AuditLog.id)).all()


def _rows(db, e):
    return db.scalars(select(WorkItem).where(WorkItem.email_id == e.id)).all()


def _raise(exc):
    def f(*a, **k):
        raise exc
    return f


# --------------------------------------------------------------------------- pipeline
def test_new_email_goes_all_the_way_and_a_second_run_changes_nothing(db, storage):
    e = _stored(db, storage, "R01-0007", "m06-a")
    assert e.status == "NEW"
    r = process_email(db, e, storage)
    assert r.stages_run == ["PARSE", "CLASSIFY", "EXTRACT", "MATCH"] and r.work_items >= 1
    assert e.status == "PROCESSED" and e.error is None
    first = sorted(w.entry_id for w in _rows(db, e))
    done = _audit(db, e, "PIPELINE_STAGE_DONE")
    assert [a.details["stage"] for a in done] == ["PARSE", "CLASSIFY", "EXTRACT", "MATCH"]
    assert all(a.actor == "system" and "ms" in a.details for a in done)

    again = process_email(db, e, storage)
    assert again.stages_run == [] and sorted(w.entry_id for w in _rows(db, e)) == first
    assert len(_audit(db, e, "PIPELINE_STAGE_DONE")) == 4


def test_failed_stage_is_recorded_and_the_retry_continues_at_that_stage(db, storage, monkeypatch):
    e = _stored(db, storage, "R01-0007", "m06-b")
    real = pipeline.extract_email
    monkeypatch.setattr(pipeline, "extract_email", _raise(RuntimeError("boom")))
    with pytest.raises(PipelineError) as exc:
        process_email(db, e, storage)
    assert exc.value.stage == "EXTRACT"
    e = db.get(EmailMessage, e.id)
    assert e.status == "FAILED" and e.error.startswith("EXTRACT: RuntimeError: boom")
    [failed] = _audit(db, e, "PIPELINE_STAGE_FAILED")
    assert failed.details["stage"] == "EXTRACT" and "boom" in failed.details["error"]
    assert [a.details["stage"] for a in _audit(db, e, "PIPELINE_STAGE_DONE")] == ["PARSE", "CLASSIFY"]

    monkeypatch.setattr(pipeline, "extract_email", real)
    r = process_email(db, e, storage)
    assert r.stages_run == ["EXTRACT", "MATCH"]  # read and classify are not repeated
    assert e.status == "PROCESSED" and e.error is None and _rows(db, e)


def test_unreadable_attachment_fails_the_parse_stage_and_is_read_again_on_retry(db, storage, monkeypatch):
    e = _stored(db, storage, "R01-0007", "m06-c")
    real = pipeline.parse_email
    monkeypatch.setattr(pipeline, "parse_email", lambda *a, **k: SimpleNamespace(failed=1, errors=["x.pdf: timeout"]))
    with pytest.raises(PipelineError) as exc:
        process_email(db, e, storage)
    assert exc.value.stage == "PARSE" and "x.pdf: timeout" in str(exc.value)
    monkeypatch.setattr(pipeline, "parse_email", real)
    e = db.get(EmailMessage, e.id)
    assert pipeline.next_stage(db, e) == "PARSE"
    assert process_email(db, e, storage).stages_run[0] == "PARSE" and e.status == "PROCESSED"


def test_resent_sample_still_becomes_duplicate_through_the_pipeline(db, storage):
    first = _stored(db, storage, "R01-0007", "m06-d1")
    process_email(db, first, storage)
    second = _stored(db, storage, "R01-0007", "m06-d2")
    process_email(db, second, storage)
    assert {w.final_classification for w in _rows(db, second)} == {"DUPLICATE"}


# --------------------------------------------------------------------------- job queue
def test_enqueue_is_one_active_job_per_email(db):
    a = jobs.enqueue(db, jobs.PROCESS_EMAIL, {"email_ref": "EML-T-1"})
    assert jobs.enqueue(db, jobs.PROCESS_EMAIL, {"email_ref": "EML-T-1"}).id == a.id
    assert jobs.enqueue(db, jobs.PROCESS_EMAIL, {"email_ref": "EML-T-2"}).id != a.id


def test_failed_job_waits_then_retries_and_gives_up_after_three_attempts(db):
    j = jobs.enqueue(db, "TEST_JOB", {"n": 1})
    for attempt, delay in ((1, 60), (2, 300)):
        got = jobs.claim_next(db, "TEST_JOB")
        assert got.id == j.id and got.status == "RUNNING" and got.attempts == attempt
        assert jobs.fail(db, got, f"error {attempt}") == "QUEUED"
        wait = (got.run_after - datetime.now(timezone.utc)).total_seconds()
        assert delay - 5 < wait <= delay
        assert jobs.claim_next(db, "TEST_JOB") is None  # not due yet
        got.run_after = datetime.now(timezone.utc)
        db.commit()
    got = jobs.claim_next(db, "TEST_JOB")
    assert got.attempts == 3 and jobs.fail(db, got, "error 3") == "FAILED"
    assert got.last_error == "error 3" and got.finished_at is not None
    assert jobs.claim_next(db, "TEST_JOB") is None
    j2 = jobs.enqueue(db, jobs.PROCESS_EMAIL, {"email_ref": "EML-T-9"})
    j2.status, j2.attempts = "FAILED", 3
    assert jobs.requeue_failed(db, "EML-T-9") == 1 and (j2.status, j2.attempts) == ("QUEUED", 0)


def test_a_claimed_job_cannot_be_claimed_twice(db):
    jobs.enqueue(db, "TEST_JOB")
    assert jobs.claim_next(db, "TEST_JOB") is not None
    assert jobs.claim_next(db, "TEST_JOB") is None


def test_job_left_running_by_a_dead_worker_is_released(db):
    j = jobs.enqueue(db, "TEST_JOB")
    got = jobs.claim_next(db, "TEST_JOB")
    got.started_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    assert jobs.release_stuck(db) >= 1
    assert j.status == "QUEUED" and "worker stopped" in j.last_error


# --------------------------------------------------------------------------- worker
def test_worker_round_processes_a_new_email_without_manual_steps(db, storage, monkeypatch):
    import app.documents.service as docs

    e = _stored(db, storage, "R01-0007", "m06-w1")
    monkeypatch.setattr(worker, "poll_gmail", lambda db_, force, summary: None)
    monkeypatch.setattr(docs, "get_storage", lambda: storage)
    s = worker.run_once(db, budget_s=600)
    assert s.queued >= 1 and s.done >= 1 and s.failed == 0
    assert db.get(EmailMessage, e.id).status == "PROCESSED" and _rows(db, e)
    assert s.line().startswith("poll skipped")


def test_worker_failure_is_retried_and_visible_on_the_job(db, storage, monkeypatch):
    e = _stored(db, storage, "R01-0007", "m06-w2")
    j = jobs.enqueue(db, jobs.PROCESS_EMAIL, {"email_ref": e.email_ref})
    monkeypatch.setattr(worker, "process_email", _raise(PipelineError("EXTRACT", "RuntimeError: forced failure")))
    s = worker.RoundSummary()
    worker.work_jobs(db, s, 60)
    assert (s.done, s.retried, s.failed) == (0, 1, 0)
    assert j.status == "QUEUED" and j.attempts == 1 and "EXTRACT: RuntimeError: forced failure" in j.last_error
    for _ in range(2):
        j.run_after = datetime.now(timezone.utc)
        db.commit()
        worker.work_jobs(db, s, 60)
    assert j.status == "FAILED" and j.attempts == 3 and s.failed == 1


def test_poll_failure_does_not_stop_processing(db, monkeypatch):
    import app.gmail.poller as poller

    monkeypatch.setattr(poller, "poll", _raise(RuntimeError("Gmail unreachable")))
    s = worker.RoundSummary()
    worker.poll_gmail(db, True, s)
    assert s.polled == "failed" and "Gmail unreachable" in s.errors[0]


# --------------------------------------------------------------------------- "Process now"
def test_process_now_needs_the_admin_key_and_starts_the_job(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_api_key", "k" * 20)
    app.dependency_overrides[get_db] = lambda: db
    try:
        c, h = TestClient(app), {"X-Admin-Key": "k" * 20}
        assert c.post("/api/admin/process-now").status_code == 401
        r = c.post("/api/admin/process-now", headers=h)  # not in Azure: nothing configured
        assert r.status_code == 409 and "python -m app.worker" in r.json()["detail"]

        called = []
        monkeypatch.setattr(azure_jobs, "start_worker_job", lambda: called.append(1) or "ar-worker-abc123")
        r = c.post("/api/admin/process-now", headers=h)
        assert r.status_code == 202 and r.json()["execution"] == "ar-worker-abc123" and called

        monkeypatch.setattr(azure_jobs, "start_worker_job",
                            _raise(azure_jobs.WorkerJobStartFailed("Azure refused to start the job (HTTP 403)")))
        assert c.post("/api/admin/process-now", headers=h).status_code == 502
        assert "counts" in c.get("/api/admin/jobs", headers=h).json()
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_start_worker_job_calls_the_job_start_endpoint_with_a_managed_identity_token(monkeypatch):
    s = get_settings()
    for k, v in (("azure_subscription_id", "sub-1"), ("azure_resource_group", "rg-x"), ("worker_job_name", "ar-worker")):
        monkeypatch.setattr(s, k, v)
    monkeypatch.setattr(azure_jobs, "_token", lambda: "TOKEN")
    seen = {}

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"name": "ar-worker-xyz"}'

    def fake_open(req, timeout):
        seen.update(url=req.full_url, method=req.get_method(), auth=req.get_header("Authorization"))
        return Resp()

    monkeypatch.setattr(azure_jobs.urllib.request, "urlopen", fake_open)
    assert azure_jobs.start_worker_job() == "ar-worker-xyz"
    assert seen["method"] == "POST" and seen["auth"] == "Bearer TOKEN"
    assert seen["url"] == ("https://management.azure.com/subscriptions/sub-1/resourceGroups/rg-x/providers/"
                           "Microsoft.App/jobs/ar-worker/start?api-version=2024-03-01")


# --------------------------------------------------------------------------- unreadable attachment, last attempt
def _fake_parse_with_one_bad_attachment(monkeypatch):
    real = pipeline.parse_email

    def parse(db, email, storage=None, **k):
        s = real(db, email, storage=storage, **k)
        s.failed, s.errors = 1, ["scan.pdf: timeout"]
        return s

    monkeypatch.setattr(pipeline, "parse_email", parse)


def test_unreadable_attachment_before_the_last_attempt_still_fails_and_retries(db, storage, monkeypatch):
    e = _stored(db, storage, "R01-0007", "m06-u1")
    _fake_parse_with_one_bad_attachment(monkeypatch)
    with pytest.raises(PipelineError) as exc:
        process_email(db, e, storage, last_attempt=False)
    assert exc.value.stage == "PARSE"


def test_last_attempt_continues_without_the_unreadable_attachment_and_sends_rows_to_review(db, storage, monkeypatch):
    e = _stored(db, storage, "R01-0007", "m06-u2")
    _fake_parse_with_one_bad_attachment(monkeypatch)
    r = process_email(db, e, storage, last_attempt=True)
    assert r.stages_run == ["PARSE", "CLASSIFY", "EXTRACT", "MATCH"] and e.status == "PROCESSED"
    assert e.error.startswith("ATTACHMENT_UNREADABLE:") and "scan.pdf: timeout" in e.error  # stays visible
    rows = [w for w in _rows(db, e) if w.decision not in ("DUPLICATE", "OUT_OF_SCOPE")]
    assert all(w.decision != "AUTO_PROCESS" and w.status != "AUTO_PROCESSED" for w in rows)
    assert all("Attachment unreadable" in w.review_reasons for w in rows)
    [a] = _audit(db, e, "ATTACHMENT_UNREADABLE_REVIEW")
    assert a.actor == "system"
    assert [x.details["stage"] for x in _audit(db, e, "PIPELINE_STAGE_DONE")][0] == "PARSE"


def test_route_to_review_downgrades_an_auto_processed_row(db, storage):
    e = _stored(db, storage, "R01-0007", "m06-u3")
    process_email(db, e, storage)
    w = _rows(db, e)[0]
    w.decision, w.status, w.sla_due_at, w.review_reasons = "AUTO_PROCESS", "AUTO_PROCESSED", None, []
    e.error = "ATTACHMENT_UNREADABLE: test"
    pipeline._route_to_review(db, e, [w])
    assert (w.decision, w.status) == ("MANUAL_REVIEW", "PENDING_REVIEW")
    assert w.review_reasons == ["Attachment unreadable"] and w.recommended_action == "Add / Update Invoice Details"
    assert w.sla_due_at is not None


def test_worker_passes_last_attempt_only_on_the_final_try(db, storage, monkeypatch):
    e = _stored(db, storage, "R01-0007", "m06-u4")
    j = jobs.enqueue(db, jobs.PROCESS_EMAIL, {"email_ref": e.email_ref})
    flags = []

    def spy(db_, email, storage=None, last_attempt=False):
        flags.append(last_attempt)
        raise PipelineError("PARSE", "x")

    monkeypatch.setattr(worker, "process_email", spy)
    s = worker.RoundSummary()
    for _ in range(3):
        j.run_after = datetime.now(timezone.utc)
        db.commit()
        worker.work_jobs(db, s, 60)
    assert flags == [False, False, True]


def test_worker_module_has_no_azure_logic():
    import inspect

    src = inspect.getsource(worker) + inspect.getsource(jobs) + inspect.getsource(pipeline)
    assert "azure" not in src.lower()
