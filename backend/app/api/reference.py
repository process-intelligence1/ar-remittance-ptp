"""Read-only access to the SAP reference data (company codes, customers, open items)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import sap

router = APIRouter(prefix="/api", tags=["SAP reference data"])

TABLES = {
    "bsid": sap.Bsid, "bsad": sap.Bsad, "kna1": sap.Kna1, "knb1": sap.Knb1, "knbk": sap.Knbk,
    "knvp": sap.Knvp, "adr6": sap.Adr6, "t001": sap.T001, "tcurx": sap.Tcurx, "t052": sap.T052,
    "tcurr": sap.Tcurr, "field_catalog": sap.FieldCatalog,
}


def _row(obj) -> dict:
    return {c.key: getattr(obj, c.key) for c in obj.__table__.columns}


@router.get("/reference/summary", summary="Row counts of every SAP reference table")
def summary(db: Session = Depends(get_db)):
    return {name: db.scalar(select(func.count()).select_from(model)) for name, model in TABLES.items()}


@router.get("/company-codes", summary="Company codes (T001)")
def company_codes(db: Session = Depends(get_db)):
    return [_row(r) for r in db.scalars(select(sap.T001).order_by(sap.T001.bukrs))]


@router.get("/customers", summary="Customers (KNA1), optionally filtered by name or number")
def customers(search: str | None = None, db: Session = Depends(get_db)):
    q = select(sap.Kna1).order_by(sap.Kna1.name1)
    if search:
        like = f"%{search}%"
        q = q.where(or_(sap.Kna1.name1.ilike(like), sap.Kna1.name2.ilike(like), sap.Kna1.kunnr.ilike(like)))
    return [_row(r) for r in db.scalars(q)]


@router.get("/customers/{kunnr}", summary="One customer with e-mails, company codes, banks and open-item totals")
def customer(kunnr: str, db: Session = Depends(get_db)):
    kunnr = kunnr.zfill(10)
    c = db.scalar(select(sap.Kna1).where(sap.Kna1.kunnr == kunnr))
    if not c:
        raise HTTPException(404, f"Customer {kunnr} not found")
    emails = db.scalars(select(sap.Adr6).where(sap.Adr6.addrnumber == c.adrnr)).all()
    company = db.scalars(select(sap.Knb1).where(sap.Knb1.kunnr == kunnr)).all()
    banks = db.scalars(select(sap.Knbk).where(sap.Knbk.kunnr == kunnr)).all()
    totals = db.execute(
        select(sap.Bsid.bukrs, sap.Bsid.waers, func.count(), func.sum(sap.Bsid.wrbtr))
        .where(sap.Bsid.kunnr == kunnr)
        .group_by(sap.Bsid.bukrs, sap.Bsid.waers)
    ).all()
    return {
        "customer": _row(c),
        "emails": [_row(e) for e in emails],
        "company_codes": [_row(k) for k in company],
        "banks": [_row(b) for b in banks],
        "open_items": [{"bukrs": b, "currency": w, "count": n, "amount": a} for b, w, n, a in totals],
    }


@router.get("/open-items", summary="Open items (BSID) with filters and paging")
def open_items(
    kunnr: str | None = None,
    bukrs: str | None = None,
    ref: str | None = Query(None, description="Invoice / reference number (searches XBLNR, BELNR, VBELN, ZUONR)"),
    currency: str | None = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = select(sap.Bsid)
    if kunnr:
        q = q.where(sap.Bsid.kunnr == kunnr.zfill(10))
    if bukrs:
        q = q.where(sap.Bsid.bukrs == bukrs)
    if currency:
        q = q.where(sap.Bsid.waers == currency.upper())
    if ref:
        like = f"%{ref}%"
        q = q.where(or_(sap.Bsid.xblnr.ilike(like), sap.Bsid.belnr.ilike(like),
                        sap.Bsid.vbeln.ilike(like), sap.Bsid.zuonr.ilike(like)))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(sap.Bsid.netdt, sap.Bsid.id).limit(limit).offset(offset)).all()
    return {"total": total, "items": [_row(r) for r in rows]}
