"""USD conversion with SAP exchange rates (sap.tcurr, rate type M) and currency decimals (sap.tcurx).

Rule: the LATEST rate on or before the row's date. No earlier rate -> no conversion: the result is None with status
NO_RATE (callers flag the row; it is never counted as 0). The amount is first rounded to the currency's decimals
(TCURX: JPY 0, KWD 3, default 2); USD = amount x ukurs x tfact / ffact, rounded to cents. USD itself needs no rate.
"""
import time
from bisect import bisect_right
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

OK, NO_RATE, NO_AMOUNT = "OK", "NO_RATE", "NO_AMOUNT"
CACHE_SECONDS = 600


def _round(value: Decimal, decimals: int) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)


class RateTable:
    def __init__(self, rates: dict[str, list[tuple[date, Decimal]]], decimals: dict[str, int] | None = None):
        # rates: currency -> [(valid from, factor to USD)] ; factor already includes tfact / ffact
        self._dates = {c: [d for d, _ in sorted(v)] for c, v in rates.items()}
        self._factors = {c: [f for _, f in sorted(v)] for c, v in rates.items()}
        self.decimals = decimals or {}

    def rate(self, currency: str, on: date) -> Decimal | None:
        dates = self._dates.get(currency)
        if not dates:
            return None
        i = bisect_right(dates, on)
        return self._factors[currency][i - 1] if i else None

    def to_usd(self, amount: Decimal | None, currency: str | None, on: date | None) -> tuple[Decimal | None, str]:
        if amount is None or not currency:
            return None, NO_AMOUNT
        amount = _round(Decimal(amount), self.decimals.get(currency, 2))
        if currency == "USD":
            return amount, OK
        factor = self.rate(currency, on) if on else None
        if factor is None:
            return None, NO_RATE
        return _round(amount * factor, 2), OK


def load_rates(db: Session) -> RateTable:
    rates: dict[str, list[tuple[date, Decimal]]] = {}
    for r in db.execute(text("select fcurr, gdatu, ukurs, ffact, tfact from sap.tcurr "
                             "where tcurr = 'USD' and kurst = 'M' and ukurs is not null")):
        factor = Decimal(r.ukurs) * Decimal(r.tfact or 1) / Decimal(r.ffact or 1)
        rates.setdefault(r.fcurr, []).append((r.gdatu, factor))
    decimals = {r.currkey: r.currdec for r in db.execute(text("select currkey, currdec from sap.tcurx"))
                if r.currdec is not None}
    return RateTable(rates, decimals)


_cache: tuple[float, RateTable] | None = None


def get_rates(db: Session) -> RateTable:
    global _cache
    if _cache is None or time.monotonic() - _cache[0] > CACHE_SECONDS:
        _cache = (time.monotonic(), load_rates(db))
    return _cache[1]
