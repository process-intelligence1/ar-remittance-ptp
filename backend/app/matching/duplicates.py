"""Duplicates (KB "Duplicate Detection"): a row is a duplicate of an earlier one when ALL of these match -
invoice number, customer, amount (within 0.01 %), currency and sender domain - and it arrived within
7 days of the original; or when the e-mail carries an attachment identical (SHA-256) to one already
processed. Only rows of the same kind are compared: a payment that follows a promise for the same
invoice (P03 -> P03R) is not a duplicate of the promise. The duplicate points to the original
(duplicate_of_id). Rule "duplicate_detection".
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class RowKey:
    row_id: int | str              # work_item.id (database) or any key (evaluation)
    email_key: int | str
    invoice_norm: str | None
    kunnr: str | None
    amount: Decimal | None
    currency: str | None
    sender_domain: str | None
    received_at: datetime | None
    attachment_hashes: frozenset[str] = frozenset()
    line_type: str | None = None   # REMITTANCE | PTP - only the same kind can be a duplicate


def same_values(new: RowKey, old: RowKey, cfg: dict) -> bool:
    if new.line_type != old.line_type:
        return False
    if not (new.invoice_norm and new.invoice_norm == old.invoice_norm and new.kunnr and new.kunnr == old.kunnr
            and new.currency == old.currency and new.sender_domain and new.sender_domain == old.sender_domain):
        return False
    if new.amount is None or old.amount is None:
        return new.amount is None and old.amount is None
    tol = abs(old.amount) * Decimal(str(cfg["amount_tolerance_pct"])) / 100
    if abs(new.amount - old.amount) > tol:
        return False
    if new.received_at and old.received_at:
        return abs((new.received_at - old.received_at).days) <= cfg["window_days"]
    return True


def find_original(new: RowKey, history: list[RowKey], cfg: dict) -> tuple[RowKey | None, str | None]:
    """(original row, reason) - history = rows of OTHER, earlier e-mails (not duplicates themselves)."""
    for old in history:
        if old.email_key == new.email_key:
            continue
        if same_values(new, old, cfg):
            return old, "same invoice, customer, amount, currency and sender domain within " \
                        f"{cfg['window_days']} days"
    if cfg.get("match_on_attachment_hash", True) and new.attachment_hashes:
        for old in history:
            if (old.email_key != new.email_key and new.line_type == old.line_type
                    and new.attachment_hashes & old.attachment_hashes
                    and (not new.invoice_norm or not old.invoice_norm or new.invoice_norm == old.invoice_norm)):
                return old, "identical attachment (SHA-256) already received"
    return None, None
