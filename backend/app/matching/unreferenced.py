"""Payments without invoice numbers (R12, R13, R28): which open invoices add up to the amount?

Search the customer's open items in the payment currency (payment-blocked items left out) for
combinations of up to `max_invoices` (6) whose sum is within `amount_tolerance_pct` (0.5 %) of the paid
amount. Fewest invoices first, then the closest sum, then the oldest invoices. The search has a time
limit; the result is ALWAYS sent to review (rule "unreferenced_payment").
"""
import time
from dataclasses import dataclass
from decimal import Decimal

from app.matching.data import OpenItem


@dataclass
class Combination:
    items: list[OpenItem]
    total: Decimal
    difference: Decimal   # total - paid amount

    @property
    def key(self):
        return (len(self.items), abs(self.difference), min(i.bldat for i in self.items))


def find_combinations(amount: Decimal | None, items: list[OpenItem], *, tolerance_pct: float, max_invoices: int,
                      time_limit_s: float = 2.0, max_results: int = 5) -> list[Combination]:
    if amount is None or amount <= 0 or not items:
        return []
    tol = amount * Decimal(str(tolerance_pct)) / 100
    pool = sorted((i for i in items if 0 < i.amount <= amount + tol), key=lambda i: i.amount, reverse=True)
    amounts = [i.amount for i in pool]
    suffix = [Decimal(0)] * (len(pool) + 1)   # sum of all items from position n on
    for n in range(len(pool) - 1, -1, -1):
        suffix[n] = suffix[n + 1] + amounts[n]
    deadline = time.perf_counter() + time_limit_s
    found: list[Combination] = []

    def search(start: int, chosen: list[int], total: Decimal, size: int) -> None:
        if time.perf_counter() > deadline or len(found) >= max_results * 20:
            return
        if len(chosen) == size:
            if abs(total - amount) <= tol:
                found.append(Combination([pool[c] for c in chosen], total, total - amount))
            return
        for n in range(start, len(pool)):
            if total + suffix[n] < amount - tol:
                return  # even all the remaining (smaller) items cannot reach the amount
            new = total + amounts[n]
            if new <= amount + tol:
                search(n + 1, chosen + [n], new, size)

    for size in range(1, max_invoices + 1):  # fewest invoices first
        search(0, [], Decimal(0), size)
        if found or time.perf_counter() > deadline:
            break
    return sorted(found, key=lambda c: c.key)[:max_results]
