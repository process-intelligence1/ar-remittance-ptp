"""Health check, business date and rule settings."""
from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models.ar import RuleConfig

router = APIRouter(prefix="/api", tags=["System"])


@router.get("/health", summary="Is the API up and can it reach the database?")
def health(db: Session = Depends(get_db)):
    db_ok = db.execute(text("SELECT 1")).scalar() == 1
    s = get_settings()
    return {"status": "ok" if db_ok else "degraded", "database": db_ok, "environment": s.environment}


@router.get("/settings/business-date", summary="The demo business date used by all rules")
def business_date(db: Session = Depends(get_db)):
    row = db.get(RuleConfig, "business_date")
    value = row.value["date"] if row else get_settings().business_date.isoformat()
    return {"business_date": value}


@router.get("/rules", summary="All tunable business rules (weights, thresholds, tolerances)")
def rules(db: Session = Depends(get_db)):
    rows = db.scalars(select(RuleConfig).order_by(RuleConfig.key)).all()
    return [{"key": r.key, "value": r.value, "description": r.description} for r in rows]
