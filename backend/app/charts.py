"""Chart data of the Dashboard (the three charts of the prototype). Pure functions: the front-end has the same
function for the demo edition (frontend/src/data/charts.ts); both are tested against one shared fixture
(data/eval/dashboard_charts_fixture.json), so live and snapshot mode show identical numbers.

Buckets of a work item: auto (Auto Processed), manual (Manual Processing), duplicates, exceptions; out-of-scope rows
(decision OUT_OF_SCOPE) belong to none. The bucket follows the row's decision only (never its workflow status).
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

CLASS_LABELS = {"REMITTANCE": "Remittance", "PTP": "Promise-to-Pay"}
DIMENSIONS = ("customer", "region", "company_code")
PERIODS = ("date", "week", "month", "quarter")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


BUCKET_BY_DECISION = {"AUTO_PROCESS": "auto", "MANUAL_REVIEW": "manual", "MANUAL_INVESTIGATION": "manual",
                      "EXCEPTION": "exceptions", "DUPLICATE": "duplicates"}


def bucket_of(decision: str | None) -> str | None:
    """Decision-based on purpose: confirming, rejecting, escalating ... a row changes its status, never its bucket."""
    return BUCKET_BY_DECISION.get(decision or "")  # OUT_OF_SCOPE / no decision: in none


@dataclass(frozen=True)
class ChartInput:
    bucket: str | None
    classification: str           # final classification: REMITTANCE | PTP | DUPLICATE | ...
    customer: str | None
    region: str | None
    company_code: str | None
    day: date | None              # e-mail received / processing date (business date for history e-mails)


def period_key(d: date, period: str) -> tuple[str, str]:
    """(sort key, label) of a date for the trend chart. Weeks are ISO weeks (Monday start)."""
    if period == "date":
        return d.isoformat(), f"{d.day} {MONTHS[d.month - 1]} {d.year}"
    if period == "week":
        y, w, _ = d.isocalendar()
        return f"{y}-W{w:02d}", f"{y}-W{w:02d}"
    if period == "month":
        return f"{d.year}-{d.month:02d}", f"{MONTHS[d.month - 1]} {d.year}"
    q = (d.month - 1) // 3 + 1
    return f"{d.year}-Q{q}", f"{d.year} Q{q}"


def _known(value: str | None) -> str | None:
    """A dimension value, or None when the record has none (such records are left out of that chart only)."""
    v = (value or "").strip()
    return None if not v or v.lower() in ("unknown", "n/a", "na", "null", "undefined", "-", "—", "(none)", "(unidentified)") else v


def build_charts(items: list[ChartInput]) -> dict:
    # 1) Performance Stability: Remittance / Promise-to-Pay stacked by Auto / Manual / Exceptions (duplicates excluded)
    perf = {c: {"auto": 0, "manual": 0, "exceptions": 0} for c in CLASS_LABELS}
    for it in items:
        if it.classification in perf and it.bucket in ("auto", "manual", "exceptions"):
            perf[it.classification][it.bucket] += 1
    performance = [{"label": CLASS_LABELS[c], **v, "total": sum(v.values())} for c, v in perf.items()]

    # 2) Distribution across Dimensions: every known value, stacked by outcome
    dims: dict[str, dict[str, dict[str, int]]] = {d: defaultdict(lambda: {"auto": 0, "manual": 0, "duplicates": 0, "exceptions": 0, "total": 0}) for d in DIMENSIONS}
    for it in items:
        for dim in DIMENSIONS:
            v = _known(getattr(it, dim))
            if v is None:
                continue
            g = dims[dim][v]
            g["total"] += 1
            if it.bucket:
                g[it.bucket] += 1
    dimensions = {
        dim: [{"label": k, **v} for k, v in sorted(groups.items(), key=lambda kv: (-kv[1]["total"], kv[0]))]
        for dim, groups in dims.items()
    }

    # 3) Processing Trend: AI processed % for Remittance and PTP per period (counts; the % is computed by the screen)
    trend: dict[str, list[dict]] = {}
    for period in PERIODS:
        buckets: dict[str, dict] = {}
        for it in items:
            if it.classification not in CLASS_LABELS or it.day is None:
                continue
            key, label = period_key(it.day, period)
            b = buckets.setdefault(key, {"key": key, "label": label, "remittance": {"total": 0, "auto": 0}, "ptp": {"total": 0, "auto": 0}})
            side = b["remittance" if it.classification == "REMITTANCE" else "ptp"]
            side["total"] += 1
            side["auto"] += it.bucket == "auto"
        trend[period] = [buckets[k] for k in sorted(buckets)]
    return {"performance": performance, "dimensions": dimensions, "trend": trend}
