"""Action endpoints (M09): single and bulk actions, e-mail preview, BSID candidates, the export list.

All need a signed-in demo user. What a user may do comes from `allowed_actions` on each row (app/permissions.py).
Every change carries the row `version`; a stale version answers 409 ("changed by someone else - refresh").
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import actions, outbound
from app.api.auth import CurrentUser, current_user
from app.api.workitems import _find, summary
from app.db import get_db
from app.fx import get_rates
from app.models.ar import EmailMessage, WorkItem

router = APIRouter(prefix="/api", tags=["Actions"])


class EmailDraft(BaseModel):
    subject: str = ""
    body: str = ""


class ActionRequest(BaseModel):
    action: str
    version: int | None = Field(None, description="the row version the user saw (summary.version)")
    comment: str | None = None
    details: dict | None = Field(None, description="Add / Update details: invoice_ref, amount, currency, payment_date, "
                                                    "payment_reference, kunnr, bukrs, bsid_id")
    email: EmailDraft | None = Field(None, description="Request Clarification: the (edited) e-mail to send")


class BulkItem(BaseModel):
    id: int | str
    version: int | None = None


class BulkRequest(BaseModel):
    action: str
    comment: str | None = None
    items: list[BulkItem]


class PreviewRequest(BaseModel):
    question: str | None = None


class ExportedRequest(BaseModel):
    entry_ids: list[str] | None = None


def _fail(exc: actions.ActionError):
    raise HTTPException(exc.status, detail={"message": exc.message, "problems": exc.problems})


def _worker_started(db: Session) -> bool:
    """Sending an e-mail starts the worker job at once (same as Process now); the 10-minute schedule is the fallback."""
    from app import azure_jobs

    if not azure_jobs.configured():
        return False
    try:
        azure_jobs.start_worker_job()
        return True
    except Exception:  # the queued job is still picked up by the schedule
        return False


@router.post("/work-items/bulk-actions", summary="One action on several records - all or nothing")
def bulk_action(body: BulkRequest, user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    items = [(_find(db, str(i.id)), i.version) for i in body.items]
    try:
        done = actions.apply_bulk(actions.Context(db), user, body.action, items, body.comment)
    except actions.ActionError as exc:
        db.rollback()
        _fail(exc)
    rates = get_rates(db)
    return jsonable_encoder({"done": len(done), "items": [summary(w, db.get(EmailMessage, w.email_id), user, rates) for w in done]})


@router.post("/work-items/{item_id}/actions", summary="Do one action on a record (audited, versioned)")
def do_action(item_id: str, body: ActionRequest, user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    w = _find(db, item_id)
    try:
        out = actions.apply_action(actions.Context(db), user, w, body.action, version=body.version, comment=body.comment,
                                   details=body.details, email=body.email.model_dump() if body.email else None)
    except actions.ActionError as exc:
        db.rollback()
        _fail(exc)
    started = _worker_started(db) if out.outbound_id else None
    return jsonable_encoder({"item": summary(w, db.get(EmailMessage, w.email_id), user, get_rates(db)),
                             "outbound_id": out.outbound_id, "worker_started": started})


@router.post("/work-items/{item_id}/outbound-preview", summary="The clarification e-mail as it would be sent (nothing is sent)")
def outbound_preview(item_id: str, body: PreviewRequest, user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    w = _find(db, item_id)
    return outbound.render_clarification(db, w, db.get(EmailMessage, w.email_id), body.question)


@router.get("/work-items/{item_id}/bsid-candidates", summary="Open BSID items to pick from (Add / Update details dialog)")
def candidates(item_id: str, q: str | None = Query(None, description="invoice no., document no., customer"),
               user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    return jsonable_encoder(actions.bsid_candidates(db, _find(db, item_id), q))


@router.get("/work-items/{item_id}/outbound", summary="E-mails sent (or queued) for a record")
def outbound_list(item_id: str, user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    from app.models.ar import OutboundMessage

    w = _find(db, item_id)
    rows = db.scalars(select(OutboundMessage).where(OutboundMessage.work_item_id == w.id).order_by(OutboundMessage.id)).all()
    return jsonable_encoder([{"id": m.id, "kind": m.kind, "subject": m.subject, "body": m.body, "status": m.status,
                              "intended_recipient": m.intended_recipient, "actual_recipient": m.actual_recipient,
                              "sent_at": m.sent_at, "error": m.error, "created_by": m.created_by,
                              "created_at": m.created_at} for m in rows])


@router.get("/exports/cases", summary="Exported cases: ALL confirmed cases with the Excel columns")
def exported_cases(user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    rows = actions.confirmed_cases(db)
    return jsonable_encoder({"count": len(rows), "columns": actions.EXPORT_COLUMNS, "items": rows})


@router.post("/exports/cases/mark-exported", summary="Record that the confirmed cases were downloaded (exported_at / exported_by)")
def mark_exported(body: ExportedRequest, user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    return {"marked": actions.mark_exported(db, user, body.entry_ids)}
