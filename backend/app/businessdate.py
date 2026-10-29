"""The demo business date (rule_config "business_date", else the BUSINESS_DATE setting).
Kept in its own tiny module so that light code (login, API start-up) does not import the Gmail libraries."""
from datetime import date

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.ar import RuleConfig


def current_business_date(db: Session) -> date:
    row = db.get(RuleConfig, "business_date")
    if row and isinstance(row.value, dict) and row.value.get("date"):
        return date.fromisoformat(row.value["date"])
    return get_settings().business_date
