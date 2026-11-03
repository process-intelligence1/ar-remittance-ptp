"""Promise-to-Pay check (M10): has each promise been kept?

Run by the worker every round and by POST /api/ptp/run. Everything uses the demo BUSINESS DATE, never the real date, and the
result is recalculated from the evidence each time, so running it twice (or after the business date moved) is safe.

For every promise (ar.ptp_commitment = one invoice or instalment) with deadline = promise date + grace_days (rule "ptp", 3):
  paid in full      -> KEPT              (received >= promised within the matching tolerance, 2 %)
  paid in part      -> PARTIALLY_KEPT
  nothing, business date > deadline                       -> BROKEN     + e-mail alert to Collections (once)
  nothing, business date > deadline + escalate_after_days -> ESCALATED  + e-mail to the AR Supervisor (once)
  otherwise         -> OPEN
"Paid" = a REMITTANCE row for the same invoice / open item (same BSID item, or same normalised invoice number and customer)
in any status except REJECTED, DUPLICATE and IGNORED, whose payment date is on or before the business date and within the
deadline. Amounts in another currency are converted with the SAP rate valid at the payment date (sap.tcurr). Several
instalments share the payments, filled in promise-date order. Alerts are e-mails through the normal outbound mechanism:
always only to OUTBOUND_REDIRECT_TO, subject "[AR-DEMO][ALERT|ESCALATION -> <role>] ...", never sent twice (flags
alerted_at / escalated_at stay when the date is moved back). SAP data is never changed.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import outbound
from app.businessdate import current_business_date
from app.config import get_settings
from app.fx import RateTable, get_rates
from app.models.ar import AppUser, AuditLog, EmailMessage, PtpCommitment, RuleConfig, WorkItem

NOT_A_PAYMENT = ("REJECTED", "DUPLICATE", "IGNORED")
FINAL = ("KEPT", "PARTIALLY_KEPT")
KIND_ALERT, KIND_ESCALATION = "ALERT", "ESCALATION"
ROLE_FOR = {KIND_ALERT: ("COLLECTIONS_ANALYST", "Collections"), KIND_ESCALATION: ("AR_SUPERVISOR", "AR Supervisor")}


def _rule(db: Session, key: str, default: dict) -> dict:
    row = db.get(RuleConfig, key)
    return {**default, **(row.value if row and isinstance(row.value, dict) else {})}


@dataclass
class Payment:
    entry_id: str
    amount: Decimal | None
    currency: str | None
    on: date
    left: Decimal | None = None          # still to give out, in `currency`
    applied: list = field(default_factory=list)  # [(commitment id, amount in the promise currency)]


@dataclass
class Result:
    business_date: date
    checked: int = 0
    changed: list[str] = field(default_factory=list)   # "ENT-000001/1: OPEN -> KEPT"
    alerts: int = 0
    escalations: int = 0
    counts: dict[str, int] = field(default_factory=dict)

    def line(self) -> str:
        return (f"PTP check at {self.business_date}: {self.checked} promise(s), {len(self.changed)} changed, "
                f"{self.alerts} alert(s), {self.escalations} escalation(s)")


def _convert(rates: RateTable, amount: Decimal, source: str | None, target: str | None, on: date) -> Decimal | None:
    """`amount` of currency `source` in `target`, at the latest rate on or before `on` (None = a rate is missing)."""
    if not source or not target or source == target:
        return amount
    f_from = Decimal(1) if source == "USD" else rates.rate(source, on)
    f_to = Decimal(1) if target == "USD" else rates.rate(target, on)
    if f_from is None or f_to is None:
        return None
    return (amount * f_from / f_to).quantize(Decimal(1).scaleb(-rates.decimals.get(target, 2)), rounding=ROUND_HALF_UP)


def _payment_date(w: WorkItem, e: EmailMessage) -> date | None:
    if w.payment_date:
        return w.payment_date
    stamp = e.received_at or e.created_at
    return stamp.date() if stamp else None


def _allocate(c: PtpCommitment, pays: list[Payment], rates: RateTable, tol: Decimal, grace: int) -> tuple[Decimal, bool, bool]:
    """Fill promise `c` from the payments (in order). Returns (received in the promise currency, no rate somewhere, amount unknown)."""
    deadline = c.promise_date + timedelta(days=grace)
    received, unconverted, unknown = Decimal(0), False, False
    for p in pays:
        if p.on > deadline or (p.left is not None and p.left <= 0):
            continue
        if c.amount is not None and received >= c.amount * (1 - tol):
            break  # already full (within tolerance)
        need = (c.amount - received) if c.amount is not None else None
        if p.left is None:  # the payment e-mail names no amount: it is taken as paying this promise in full
            give = need if need is not None else Decimal(0)
            unknown = True
            p.left = Decimal(0)
        else:
            avail = _convert(rates, p.left, p.currency, c.currency, p.on)
            if avail is None:
                unconverted = True
                continue
            give = avail if need is None else min(avail, need)
            leftover = avail - give
            dust = (c.amount or Decimal(0)) * tol
            if leftover <= dust:
                p.left = Decimal(0)  # within tolerance: nothing meaningful is left for the next instalment
            else:  # convert what was used back to the payment currency
                used = _convert(rates, give, c.currency, p.currency, p.on)
                p.left = p.left - used if used is not None else Decimal(0)
        received += give
        if give > 0 or unknown:
            p.applied.append((c.id, give))
    return received, unconverted, unknown


def _queue_alert(db: Session, kind: str, c: PtpCommitment, w: WorkItem, e: EmailMessage, business_date: date,
                 deadline: date, received: Decimal | None) -> bool:
    """Queue the alert e-mail. Returns False when none is sent (history e-mails)."""
    if e.source == "history":
        return False  # M11: promises of the built-in history are flagged as alerted, but no e-mail is ever sent for them
    role, label = ROLE_FOR[kind]
    who = db.scalar(select(AppUser.email).where(AppUser.role == role, AppUser.active.is_(True)).order_by(AppUser.id).limit(1)) or label
    what = f"{c.currency or ''} {c.amount:,.2f}".strip() if c.amount is not None else "(amount not stated)"
    inst = f" (instalment {c.instalment_no})" if (c.instalment_no or 1) > 1 else ""
    headline = "Promise to pay broken" if kind == KIND_ALERT else "Broken promise escalated to the AR Supervisor"
    subject = f"[AR-DEMO][{kind} → {label}] {headline}: {w.customer_name or 'customer'}, invoice {w.invoice_ref_raw or '-'}{inst}"
    body = (f"[AR-DEMO] In production this e-mail would go to {who}. Demo mode: it is delivered to "
            f"{get_settings().outbound_redirect_to} only.\n\n"
            f"{headline}.\n\nCustomer: {w.customer_name or '(unidentified)'} ({(w.kunnr or '').lstrip('0') or '-'})\n"
            f"Invoice: {w.invoice_ref_raw or '-'}{inst}\nPromised: {what} by {c.promise_date.isoformat()}\n"
            f"Grace period ended: {deadline.isoformat()}   Business date: {business_date.isoformat()}\n"
            f"Received so far: {received if received else 0} {c.currency or ''}\n"
            f"Record: {w.entry_id} (e-mail {e.email_ref}) - open it in the Action Queue / PTP Tracker.\n")
    outbound.queue_message(db, w, e, subject=subject, body=body, created_by="system", kind=kind, intended=who)
    return True


def evaluate(db: Session, *, actor: str = "system", actor_role: str | None = None) -> Result:
    """Check every promise at the business date; writes status, evidence, audit entries and the (once-only) alert e-mails."""
    bd = current_business_date(db)
    rules = _rule(db, "ptp", {"grace_days": 3, "escalate_after_days": 2})
    grace, escalate_after = int(rules["grace_days"]), int(rules["escalate_after_days"])
    tol = Decimal(str(_rule(db, "fast_path", {"amount_tolerance_pct": 2})["amount_tolerance_pct"])) / 100
    rates = get_rates(db)
    out = Result(business_date=bd)

    promises = db.execute(select(PtpCommitment, WorkItem, EmailMessage)
                          .join(WorkItem, WorkItem.id == PtpCommitment.work_item_id)
                          .join(EmailMessage, EmailMessage.id == WorkItem.email_id)
                          .order_by(PtpCommitment.promise_date, PtpCommitment.instalment_no, PtpCommitment.id)).all()
    norms = {w.invoice_ref_norm for _, w, _ in promises if w.invoice_ref_norm}
    bsids = {c.bsid_id for c, _, _ in promises if c.bsid_id}
    pay_rows = db.execute(
        select(WorkItem, EmailMessage).join(EmailMessage, EmailMessage.id == WorkItem.email_id)
        .where(WorkItem.line_type == "REMITTANCE", WorkItem.status.not_in(NOT_A_PAYMENT),
               or_(WorkItem.invoice_ref_norm.in_(norms or {""}), WorkItem.bsid_id.in_(bsids or {-1})))).all()
    by_norm, by_bsid = defaultdict(list), defaultdict(list)
    for pw, pe in pay_rows:
        on = _payment_date(pw, pe)
        if on is None or on > bd:
            continue  # not paid yet at the business date
        pay = (pw, Payment(pw.entry_id, pw.amount, pw.currency, on, pw.amount), pw.kunnr)
        if pw.invoice_ref_norm:
            by_norm[pw.invoice_ref_norm].append(pay)
        if pw.bsid_id:
            by_bsid[pw.bsid_id].append(pay)

    # promises of the same invoice share the payments (instalments filled in promise-date order)
    groups: dict[tuple, list] = defaultdict(list)
    for c, w, e in promises:
        groups[(w.kunnr or "", w.invoice_ref_norm or (f"b{c.bsid_id}" if c.bsid_id else f"w{w.id}"))].append((c, w, e))

    for (kunnr, _), items in groups.items():
        found = {}
        for c0, w0, _e in items:  # same open item, or same invoice number, same customer
            candidates = (by_bsid.get(c0.bsid_id, []) if c0.bsid_id else []) + (by_norm.get(w0.invoice_ref_norm, []) if w0.invoice_ref_norm else [])
            for pw, pay, pkunnr in candidates:
                if kunnr and pkunnr and pkunnr != kunnr:
                    continue
                found[pw.id] = pay
        pays = sorted(found.values(), key=lambda p: (p.on, p.entry_id))
        for c, w, e in items:
            out.checked += 1
            before = c.status
            if w.status == "REJECTED":
                new, received, note, unconverted = "CANCELLED", c.amount_received, "The promise record was rejected", False
            else:
                received, unconverted, unknown = _allocate(c, pays, rates, tol, grace)
                deadline = c.promise_date + timedelta(days=grace)
                full = (received > 0 or unknown) if c.amount is None else received >= c.amount * (1 - tol)
                note = None
                if full:
                    new = "KEPT"
                elif received > 0:
                    new = "PARTIALLY_KEPT"
                elif unconverted:
                    new, note = "OPEN", "A payment was found but cannot be converted (no exchange rate for its currency)"
                elif bd > deadline + timedelta(days=escalate_after):
                    new = "ESCALATED"
                elif bd > deadline:
                    new = "BROKEN"
                else:
                    new = "OPEN"
                if unknown and note is None:
                    note = "A payment was found but its e-mail names no amount: taken as paid in full"
            deadline = c.promise_date + timedelta(days=grace)
            applied = [{"entry_id": p.entry_id, "amount": str(p.amount) if p.amount is not None else None, "currency": p.currency,
                        "date": p.on.isoformat(), "applied": str(sum(a for cid, a in p.applied if cid == c.id))}
                       for p in pays if any(cid == c.id for cid, _ in p.applied)]
            c.payments, c.check_note, c.last_checked_on = applied or None, note, bd
            c.amount_received = received if (received and received > 0) else None
            c.broken_on = deadline + timedelta(days=1)
            if new == "KEPT":
                c.closed_at = c.closed_at or datetime.now(timezone.utc)
            else:
                c.closed_at = None
            if new != before:
                c.status = new
                out.changed.append(f"{w.entry_id}/{c.instalment_no}: {before} -> {new}")
                db.add(AuditLog(business_date=bd, actor=actor, actor_role=actor_role, entity_type="ptp",
                                entity_id=f"{w.entry_id}/{c.instalment_no}"[:40], action=f"PTP_{new}",
                                details={"before": {"status": before}, "after": {"status": new},
                                         "promise_date": c.promise_date.isoformat(), "deadline": deadline.isoformat(),
                                         "received": str(received) if received else None, "payments": applied or None}))
            # alerts: once per event; a promise that jumped straight to ESCALATED sends both
            if new in ("BROKEN", "ESCALATED") and c.alerted_at is None:
                sent = _queue_alert(db, KIND_ALERT, c, w, e, bd, deadline, received)
                c.alerted_at = datetime.now(timezone.utc)
                out.alerts += sent
            if new == "ESCALATED" and c.escalated_at is None:
                sent = _queue_alert(db, KIND_ESCALATION, c, w, e, bd, deadline, received)
                c.escalated_at = datetime.now(timezone.utc)
                out.escalations += sent
    db.commit()
    out.counts = {s: n for s, n in db.execute(select(PtpCommitment.status, func.count()).group_by(PtpCommitment.status)).all()}
    return out

