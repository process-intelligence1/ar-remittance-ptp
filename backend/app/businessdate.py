"""The demo business date (rule_config "business_date", else the BUSINESS_DATE setting).
Kept in its own tiny module so that light code (login, API start-up) does not import the Gmail libraries."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.ar import RuleConfig


_override: ContextVar[date | None] = ContextVar("business_date_override", default=None)


@contextmanager
def override_business_date(day: date):
    """Inside the block THIS process sees `day` as the business date; nothing is stored, other processes are not affected
    (scripts.build_history uses it while it builds three months of history inside a system that keeps running)."""
    token = _override.set(day)
    try:
        yield
    finally:
        _override.reset(token)


def current_business_date(db: Session) -> date:
    if (forced := _override.get()) is not None:
        return forced
    row = db.get(RuleConfig, "business_date")
    if row and isinstance(row.value, dict) and row.value.get("date"):
        return date.fromisoformat(row.value["date"])
    return get_settings().business_date
