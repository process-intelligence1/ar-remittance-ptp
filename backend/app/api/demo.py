"""Demo Control API (M11): state, send a live-set sample, move the business date, Process now, Reset demo.

Any signed-in demo user may use it (the demo access code is the gate); Reset needs "confirm": true in the request, which the
screen asks for in a confirmation dialog.
"""
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import demo
from app.api.auth import CurrentUser, current_user
from app.db import get_db

router = APIRouter(prefix="/api/demo", tags=["Demo Control"])


class SendSampleRequest(BaseModel):
    code: str
    process_now: bool = True


class BusinessDateRequest(BaseModel):
    date: dt.date | None = None
    add_days: int | None = None


class ResetRequest(BaseModel):
    confirm: bool = False


def _fail(exc: demo.DemoError):
    raise HTTPException(exc.status, detail=exc.message)


def _start_worker() -> dict:
    """Start the worker job at once (same mechanism as /api/admin/process-now, but for a signed-in user)."""
    from app import azure_jobs

    if not azure_jobs.configured():
        return {"started": False, "reason": "No Azure worker job here - on the laptop run: python -m app.worker --once"}
    try:
        return {"started": True, "execution": azure_jobs.start_worker_job()}
    except Exception as exc:  # the 10-minute schedule still picks the work up
        return {"started": False, "reason": f"{type(exc).__name__}: {exc}"}


@router.get("/state", summary="Demo Control: business date, reset point, the live set with what was already sent")
def get_state(user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    return jsonable_encoder(demo.state(db))


@router.post("/send-sample", summary="Put a live-set sample into the Gmail inbox (customer as sender), optionally start the worker")
def send_sample(body: SendSampleRequest, user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    try:
        sent = demo.send_sample(db, user, body.code)
    except demo.DemoError as exc:
        db.rollback()
        _fail(exc)
    db.commit()
    return jsonable_encoder({**sent, "worker": _start_worker() if body.process_now else None})


@router.post("/process-now", summary="Start the worker job now: read Gmail and process what is waiting")
def process_now(user: CurrentUser = Depends(current_user)):
    return _start_worker()


@router.post("/business-date", summary="Move the demo business date (a date or +N days); promises to pay are checked at once")
def business_date(body: BusinessDateRequest, user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    try:
        result = demo.set_business_date(db, user, day=body.date, add_days=body.add_days)
    except demo.DemoError as exc:
        db.rollback()
        _fail(exc)
    db.commit()
    alerts = result["ptp"]["alerts"] + result["ptp"]["escalations"]
    return jsonable_encoder({**result, "worker": _start_worker() if alerts else None})  # alert e-mails go out right away


@router.post("/reset", summary="Reset demo: restore everything to the reset point (statuses, exports, promises, samples sent, date)")
def reset(body: ResetRequest, user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    if not body.confirm:
        raise HTTPException(422, detail="Resetting needs confirm = true.")
    try:
        result = demo.restore_reset_point(db, user)
    except demo.DemoError as exc:
        db.rollback()
        _fail(exc)
    db.commit()
    return jsonable_encoder(result)
