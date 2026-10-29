"""Dashboard KPIs / charts (M07) and the Audit Trail list.

KPIs use the same filters as the work-item list. Amounts are converted to USD (app/fx.py: latest rate on or before the
row date, TCURX decimals). Rows with no rate are counted in `usd.unconverted` and left out of the USD sums - never 0.
"""
from collections import defaultdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.api.auth import CurrentUser, current_user
from app.api.workitems import MAX_PAGE, Filters, apply_filters, columns, filters, row_date
from app.db import get_db
from app.fx import NO_AMOUNT, OK, get_rates
from app.models.ar import AuditLog, EmailMessage, WorkItem

router = APIRouter(prefix="/api", tags=["Dashboard and audit"])

TOP_CUSTOMERS = 10


def bucket(w: WorkItem) -> str:
    """The Dashboard's processing buckets."""
    if w.status == "DUPLICATE":
        return "duplicates"
    if w.status == "EXCEPTION":
        return "exceptions"
    if w.status == "AUTO_PROCESSED" or (w.status == "RESOLVED" and (w.resolved_by or "system") == "system"):
        return "ai"
    if w.status in ("PENDING_REVIEW", "RESOLVED", "REJECTED"):
        return "manual"
    return "other"  # IGNORED (out of scope)


def _r(x: Decimal | None) -> float | None:
    return None if x is None else round(float(x), 2)


@router.get("/kpis", summary="Dashboard: KPI cards, distributions, monthly trend, performance stability")
def kpis(f: Filters = Depends(filters), user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(apply_filters(select(WorkItem, EmailMessage).join(EmailMessage, EmailMessage.id == WorkItem.email_id), f)).all()
    rates = get_rates(db)

    cards = {k: {"count": 0, "usd": Decimal(0)} for k in ("total", "ai", "manual", "duplicates", "exceptions")}
    dims = {k: defaultdict(lambda: {"count": 0, "usd": Decimal(0)}) for k in
            ("customer", "region", "company_code", "classification", "status")}
    months: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "ai": 0, "manual": 0, "duplicates": 0, "exceptions": 0})
    days: dict[date, list] = defaultdict(lambda: [0, 0, Decimal(0), 0])  # rows, ai, confidence sum, confidence n
    unconverted, missing = 0, defaultdict(int)

    for w, e in rows:
        on = row_date(w, e)
        usd, status = rates.to_usd(w.amount, w.currency, on)
        if status != OK and status != NO_AMOUNT:
            unconverted += 1
            missing[w.currency] += 1
        b = bucket(w)
        keys = ["total"] + ([b] if b in cards else [])
        for k in keys:
            cards[k]["count"] += 1
            if usd is not None:
                cards[k]["usd"] += usd
        values = {"customer": w.customer_name or "(unidentified)", "region": w.region or "(none)",
                  "company_code": w.bukrs or "(none)", "classification": w.final_classification, "status": w.status}
        for dim, v in values.items():
            dims[dim][v]["count"] += 1
            if usd is not None:
                dims[dim][v]["usd"] += usd
        if on:
            m = months[on.strftime("%Y-%m")]
            m["total"] += 1
            if b in m:
                m[b] += 1
            d = days[on]
            d[0] += 1
            d[1] += b == "ai"
            if w.confidence_score is not None:
                d[2] += w.confidence_score
                d[3] += 1

    def dist(name: str, top: int | None = None) -> list[dict]:
        items = sorted(dims[name].items(), key=lambda kv: (-kv[1]["count"], kv[0]))
        out = [{"label": k, "count": v["count"], "usd": _r(v["usd"])} for k, v in items]
        if top and len(out) > top:
            rest = out[top:]
            out = out[:top] + [{"label": "Other", "count": sum(x["count"] for x in rest), "usd": _r(sum(Decimal(str(x["usd"] or 0)) for x in rest))}]
        return out

    return jsonable_encoder({
        "cards": {k: {"count": v["count"], "usd": _r(v["usd"])} for k, v in cards.items()},
        "usd": {"unconverted": unconverted, "missing_rate_currencies": dict(missing),
                "note": "Rows without an exchange rate are not included in USD sums."},
        "distributions": {"customer": dist("customer", TOP_CUSTOMERS), "region": dist("region"),
                          "company_code": dist("company_code"), "classification": dist("classification"),
                          "status": dist("status")},
        "monthly_trend": [{"month": m, **v} for m, v in sorted(months.items())],
        "performance_stability": [
            {"date": d, "rows": v[0], "auto_rate": round(v[1] / v[0], 4) if v[0] else None,
             "avg_confidence": round(float(v[2] / v[3]), 2) if v[3] else None} for d, v in sorted(days.items())],
    })


@router.get("/audit", summary="Audit Trail: who did what, when (filters as in the prototype)")
def audit(from_date: date | None = None, to_date: date | None = None, actor: str | None = None,
          action: str | None = None, entity_type: str | None = None, entity_id: str | None = None,
          q: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=MAX_PAGE),
          user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    c = []
    if from_date:
        c.append(func.date(AuditLog.occurred_at) >= from_date)
    if to_date:
        c.append(func.date(AuditLog.occurred_at) <= to_date)
    if actor:
        c.append(AuditLog.actor.ilike(f"%{actor}%"))
    if action:
        c.append(AuditLog.action == action.upper())
    if entity_type:
        c.append(AuditLog.entity_type == entity_type)
    if entity_id:
        c.append(AuditLog.entity_id == entity_id)
    if q:
        c.append(or_(AuditLog.entity_id.ilike(f"%{q}%"), AuditLog.action.ilike(f"%{q}%"), AuditLog.actor.ilike(f"%{q}%")))
    where = and_(*c) if c else True
    total = db.scalar(select(func.count()).select_from(AuditLog).where(where))
    items = db.scalars(select(AuditLog).where(where).order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
                       .limit(page_size).offset((page - 1) * page_size)).all()
    return jsonable_encoder({"total": total, "page": page, "page_size": page_size,
                             "items": [columns(a) for a in items]})
