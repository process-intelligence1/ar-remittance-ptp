"""PTP Tracker API (M10): every promise to pay with its status, and a way to re-check at the business date.

Needs a signed-in demo user. POST /api/ptp/run runs the same check as the worker (idempotent; alert e-mails go out at most
once per promise and event), so after the business date was moved the Tracker can be brought up to date at once.
"""
from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import ptp
from app.api.auth import CurrentUser, current_user
from app.businessdate import current_business_date
from app.db import get_db
from app.models.ar import EmailMessage, PtpCommitment, RuleConfig, WorkItem

router = APIRouter(prefix="/api", tags=["Promise to pay"])
STATUSES = ("OPEN", "PARTIALLY_KEPT", "KEPT", "BROKEN", "ESCALATED", "CANCELLED")


@router.get("/ptp", summary="PTP Tracker: promises with status, deadline, payments found and alerts")
def list_ptp(status: str | None = None, customer: str | None = Query(None, description="customer number or part of the name"),
             q: str | None = Query(None, description="entry id, invoice number, customer"),
             page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=200),
             user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    bd = current_business_date(db)
    grace = int(((db.get(RuleConfig, "ptp") or RuleConfig(value={})).value or {}).get("grace_days", 3))
    base = (select(PtpCommitment, WorkItem, EmailMessage).join(WorkItem, WorkItem.id == PtpCommitment.work_item_id)
            .join(EmailMessage, EmailMessage.id == WorkItem.email_id))
    if status:
        base = base.where(PtpCommitment.status == status.upper())
    if customer:
        k = customer.strip()
        base = base.where(or_(WorkItem.kunnr == k.zfill(10), WorkItem.kunnr == k, WorkItem.customer_name.ilike(f"%{k}%")))
    if q:
        like = f"%{q.strip()}%"
        base = base.where(or_(WorkItem.entry_id.ilike(like), WorkItem.invoice_ref_raw.ilike(like), WorkItem.customer_name.ilike(like)))
    total = db.scalar(select(func.count()).select_from(base.with_only_columns(PtpCommitment.id).subquery()))
    rows = db.execute(base.order_by(PtpCommitment.promise_date, PtpCommitment.id).limit(page_size).offset((page - 1) * page_size)).all()
    counts = {s: n for s, n in db.execute(select(PtpCommitment.status, func.count()).group_by(PtpCommitment.status))}
    items = []
    for c, w, e in rows:
        deadline = c.promise_date + timedelta(days=grace)
        items.append({
            "id": c.id, "work_item_id": w.id, "entry_id": w.entry_id, "email_ref": e.email_ref, "sender_email": e.sender_email,
            "customer_name": w.customer_name, "kunnr": w.kunnr, "company_code": w.bukrs, "invoice_ref": w.invoice_ref_raw,
            "instalment_no": c.instalment_no, "promise_date": c.promise_date, "deadline": deadline,
            "amount": c.amount, "currency": c.currency, "status": c.status, "amount_received": c.amount_received,
            "days_overdue": max(0, (bd - c.promise_date).days) if c.status not in ("KEPT", "CANCELLED") else 0,
            "payments": c.payments or [], "alerted_at": c.alerted_at, "escalated_at": c.escalated_at,
            "check_note": c.check_note, "last_checked_on": c.last_checked_on})
    return jsonable_encoder({"business_date": bd, "grace_days": grace, "total": total, "page": page, "page_size": page_size,
                             "counts": {s: counts.get(s, 0) for s in STATUSES}, "items": items})


@router.post("/ptp/run", summary="Check every promise now at the business date (same as the worker; safe to repeat)")
def run_ptp(user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    r = ptp.evaluate(db, actor=user.email, actor_role=user.role)
    return jsonable_encoder({"business_date": r.business_date, "checked": r.checked, "changed": r.changed,
                             "alerts": r.alerts, "escalations": r.escalations, "counts": r.counts})
