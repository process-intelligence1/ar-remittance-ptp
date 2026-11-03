"""Analyst actions on work items (M09), the export list for "Confirm & Add to Excel", and their audit entries.

Rules
- The caller must send the row `version` it was looking at; if somebody changed the row since, nothing happens (409).
- The action must be in `allowed_actions` for the user's role (403 otherwise).
- Every action writes ONE audit entry with before / after values, the comment, who and when.
- SAP data (sap.*) is never changed. "Confirm & Add to Excel" only sets the status CONFIRMED; the Excel file is the posting file.
- Statuses never change a row's decision, so the Dashboard (which counts by decision) does not move.
- Re-matching actions (Add / Update details, Add BSID details, Mark as Non-Duplicate) calculate the row again with the
  normal scoring, so they may change the decision - that is a new result, not a status change.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import outbound
from app.api.auth import CurrentUser
from app.businessdate import current_business_date
from app.models.ar import AuditLog, EmailMessage, WorkItem
from app.permissions import (ADD_BSID, CLARIFY, CLOSE_DUP, CONFIRM, EDIT, ESCALATE, NOT_DUP, REJECT, STATUS_AFTER,
                             SUPERVISOR, allowed_actions)

BULK_ACTIONS = (CONFIRM, REJECT, ESCALATE, CLOSE_DUP)   # need no per-row input
COMMENT_REQUIRED = (REJECT, ESCALATE)
EDITABLE = ("invoice_ref", "amount", "currency", "payment_date", "payment_reference", "kunnr", "bukrs")  # Add / Update details
SCORE_FIELDS = ("decision", "status", "confidence_score", "confidence_source", "match_level", "bsid_id", "kunnr", "bukrs",
                "invoice_ref_raw", "amount", "currency", "payment_date", "remittance_ref", "assigned_role")
STALE = "This record was changed by someone else - refresh and try again."


def snapshot(w: WorkItem) -> dict:
    """The values an audit entry records before and after an action."""
    return {k: (str(v) if isinstance(v, (Decimal, date)) else v) for k in SCORE_FIELDS for v in [getattr(w, k)]}


class ActionError(Exception):
    def __init__(self, status: int, message: str, problems: list[dict] | None = None):
        super().__init__(message)
        self.status, self.message, self.problems = status, message, problems or []


@dataclass
class Outcome:
    item: WorkItem
    outbound_id: int | None = None


@dataclass
class Context:
    """Things that are expensive to load; shared by the rows of one request."""
    db: Session
    _sap: object = field(default=None, repr=False)
    _rules: dict | None = None

    @property
    def sap(self):
        if self._sap is None:
            from app.matching.data import load_sap  # lazy: the slim API image must start without the heavy libraries

            self._sap = load_sap(self.db)
        return self._sap

    @property
    def rules(self) -> dict:
        if self._rules is None:
            from app.matching.service import all_rules

            self._rules = all_rules(self.db)
        return self._rules


def now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- checks
def confirm_problems(w: WorkItem) -> list[str]:
    """Why a row cannot be added to the Excel list yet (empty = fine)."""
    problems = []
    if not w.invoice_ref_norm:
        problems.append("invoice number missing")
    if not w.kunnr:
        problems.append("customer not identified")
    if not w.bsid_match_flag and w.amount is None:
        problems.append("needs a BSID match or an amount")
    return problems


def check(user: CurrentUser, w: WorkItem, action: str, version: int | None, comment: str | None = None) -> tuple[int, str] | None:
    """(status code, message) when the action cannot be done on this row, else None."""
    if version is None or w.row_version != version:
        return 409, STALE
    if action not in allowed_actions(user.role, w.decision, w.status, w.assigned_role, bool(w.resolved_at)):
        return 403, f"{action} is not available for this record and role."
    if action in COMMENT_REQUIRED and not (comment or "").strip():
        return 422, "A comment is required for this action."
    if action == CONFIRM and (p := confirm_problems(w)):
        return 422, "Cannot confirm: " + ", ".join(p) + "."
    if action == NOT_DUP and not w.duplicate_of_id:
        return 422, "This record is not marked as a duplicate."
    return None


# --------------------------------------------------------------------------- one action
def _audit(db: Session, user: CurrentUser, w: WorkItem, action: str, before: dict, comment: str | None, **extra) -> None:
    db.add(AuditLog(business_date=current_business_date(db), actor=user.email, actor_role=user.role, entity_type="work_item",
                    entity_id=w.entry_id, action=action,
                    details={"before": before, "after": snapshot(w), "comment": (comment or None), **extra}))


def apply_action(ctx: Context, user: CurrentUser, w: WorkItem, action: str, *, version: int | None, comment: str | None = None,
                 details: dict | None = None, email: dict | None = None, commit: bool = True) -> Outcome:
    db = ctx.db
    if (err := check(user, w, action, version, comment)):
        raise ActionError(*err)
    comment = (comment or "").strip() or None
    before = snapshot(w)
    out = Outcome(w)
    stamp = now()

    if action in (EDIT, ADD_BSID, NOT_DUP):
        from app.matching.rescore import DetailsError, Edit, rescore

    if action in (EDIT, ADD_BSID):
        details = details or {}
        values = {k: details[k] for k in EDITABLE if k in details}
        bsid_id = details.get("bsid_id")
        if not values and not bsid_id:
            raise ActionError(422, "Nothing to save - change a field or select a BSID item.")
        e = db.get(EmailMessage, w.email_id)
        try:
            rescore(db, w, e, Edit(values, int(bsid_id) if bsid_id else None), ctx.sap, ctx.rules, current_business_date(db))
        except DetailsError as exc:
            raise ActionError(422, str(exc)) from exc
        w.action_comment = comment
        _audit(db, user, w, action, before, comment, changed=sorted(values) + (["bsid_id"] if bsid_id else []))
    elif action == NOT_DUP:
        e = db.get(EmailMessage, w.email_id)
        original = w.duplicate_of_id
        rescore(db, w, e, Edit({}), ctx.sap, ctx.rules, current_business_date(db), drop_duplicate=True)
        w.action_comment = comment
        _audit(db, user, w, action, before, comment, was_duplicate_of=original)
    else:
        extra: dict = {}
        if action == CLARIFY:
            e = db.get(EmailMessage, w.email_id)
            try:
                msg = outbound.queue_message(db, w, e, subject=(email or {}).get("subject", ""), body=(email or {}).get("body", ""),
                                             created_by=user.email)
            except outbound.OutboundError as exc:
                raise ActionError(422, str(exc)) from exc
            out.outbound_id = msg.id
            extra = {"outbound_id": msg.id, "subject": msg.subject, "intended_recipient": msg.intended_recipient,
                     "actual_recipient": msg.actual_recipient}
        w.status = STATUS_AFTER[action]
        w.action_comment = comment
        if action == ESCALATE:
            w.assigned_role = SUPERVISOR
        if action in (CONFIRM, REJECT, CLOSE_DUP):
            w.resolved_at, w.resolved_by = stamp, user.email
        if action == CONFIRM:
            w.confirmed_at, w.confirmed_by = stamp, user.email
        _audit(db, user, w, action, before, comment, **extra)
    db.flush()
    if commit:
        db.commit()
    return out


def apply_bulk(ctx: Context, user: CurrentUser, action: str, items: list[tuple[WorkItem, int | None]],
               comment: str | None) -> list[WorkItem]:
    """All or nothing: when ANY selected row is not valid for the action, no row is changed."""
    if action not in BULK_ACTIONS:
        raise ActionError(422, f"{action} cannot be done on several records at once.")
    if not items:
        raise ActionError(422, "Select at least one record.")
    problems = []
    for w, version in items:
        if (err := check(user, w, action, version, comment)):
            problems.append({"entry_id": w.entry_id, "status": err[0], "message": err[1]})
    if problems:
        code = 409 if all(p["status"] == 409 for p in problems) else 422
        raise ActionError(code, f"{len(problems)} of {len(items)} selected records cannot be processed - nothing was changed.", problems)
    done = [apply_action(ctx, user, w, action, version=v, comment=comment, commit=False).item for w, v in items]
    ctx.db.commit()
    return done


# --------------------------------------------------------------------------- BSID candidates (Add / Update details dialog)
def bsid_candidates(db: Session, w: WorkItem, q: str | None, limit: int = 40) -> list[dict]:
    """Open BSID items the analyst can pick: the automatic candidates first, then the customer's open items, then a search."""
    cols = ("b.id, b.bukrs, b.kunnr, b.belnr, b.gjahr, b.buzei, b.xblnr, b.vbeln, b.wrbtr, b.waers, b.shkzg, b.bldat, b.zfbdt, "
            "trim(coalesce(k.name1, '')) as customer_name")
    base = f"select {cols} from sap.bsid b left join sap.kna1 k on k.kunnr = b.kunnr"
    rows: dict[int, dict] = {}

    def add(sql: str, params: dict, source: str) -> None:
        for r in db.execute(text(sql), params):
            rows.setdefault(r.id, {**dict(r._mapping), "source": source})

    add(f"{base} join ar.match_candidate c on c.bsid_id = b.id and c.work_item_id = :w order by c.rank", {"w": w.id}, "candidate")
    term = (q or "").strip()
    if term:
        add(f"{base} where b.xblnr ilike :t or b.belnr ilike :t or b.vbeln ilike :t or k.name1 ilike :t "
            f"or b.kunnr = lpad(:raw, 10, '0') order by b.bldat desc limit :n", {"t": f"%{term}%", "raw": term, "n": limit}, "search")
    elif w.kunnr:
        add(f"{base} where b.kunnr = :k order by b.bldat desc limit :n", {"k": w.kunnr, "n": limit}, "customer")
    out = list(rows.values())[:limit]
    for r in out:
        r["amount"] = -r["wrbtr"] if r["shkzg"] == "H" else r["wrbtr"]
        r["selected"] = r["id"] == w.bsid_id
    return out


# --------------------------------------------------------------------------- export list ("Exported cases")
EXPORT_COLUMNS = ("entry_id", "email_ref", "received_at", "sender_email", "kunnr", "customer_name", "company_code", "invoice_ref",
                  "belnr", "gjahr", "buzei", "invoice_amount", "invoice_currency", "paid_amount", "paid_currency", "difference",
                  "payment_date", "payment_reference", "match_level", "confidence", "decision", "confirmed_by", "confirmed_at",
                  "comment", "exported_at", "exported_by")


def confirmed_cases(db: Session) -> list[dict]:
    """ALL confirmed cases, oldest confirmation first (the rows of the Excel view)."""
    rows = db.execute(select(WorkItem, EmailMessage).join(EmailMessage, EmailMessage.id == WorkItem.email_id)
                      .where(WorkItem.status == "CONFIRMED").order_by(WorkItem.confirmed_at, WorkItem.id)).all()
    ids = [w.bsid_id for w, _ in rows if w.bsid_id]
    bsid = {r.id: r for r in db.execute(text("select id, belnr, gjahr, buzei, wrbtr, waers, shkzg from sap.bsid where id = any(:ids)"),
                                        {"ids": ids})} if ids else {}
    out = []
    for w, e in rows:
        b = bsid.get(w.bsid_id)
        inv_amount = (-b.wrbtr if b.shkzg == "H" else b.wrbtr) if b else None
        same_cur = b is not None and (not w.currency or w.currency == b.waers)
        out.append({
            "entry_id": w.entry_id, "email_ref": e.email_ref, "received_at": e.received_at, "sender_email": e.sender_email,
            "kunnr": w.kunnr.lstrip("0") if w.kunnr else None, "customer_name": w.customer_name, "company_code": w.bukrs,
            "invoice_ref": w.invoice_ref_raw, "belnr": b.belnr if b else None, "gjahr": b.gjahr if b else None,
            "buzei": b.buzei if b else None, "invoice_amount": inv_amount, "invoice_currency": b.waers if b else None,
            "paid_amount": w.amount, "paid_currency": w.currency or (b.waers if b else None),
            "difference": (w.amount - inv_amount) if (w.amount is not None and inv_amount is not None and same_cur) else None,
            "payment_date": w.payment_date, "payment_reference": w.remittance_ref, "match_level": w.match_level,
            "confidence": w.confidence_score, "decision": w.decision, "confirmed_by": w.confirmed_by,
            "confirmed_at": w.confirmed_at, "comment": w.action_comment, "exported_at": w.exported_at,
            "exported_by": w.exported_by})
    return out


def mark_exported(db: Session, user: CurrentUser, entry_ids: list[str] | None = None) -> int:
    """Record that these confirmed cases were downloaded (all of them when no ids are given). Re-download is allowed."""
    q = select(WorkItem).where(WorkItem.status == "CONFIRMED")
    if entry_ids:
        q = q.where(WorkItem.entry_id.in_(entry_ids))
    rows = db.scalars(q).all()
    stamp = now()
    for w in rows:
        before = {"exported_at": str(w.exported_at) if w.exported_at else None, "exported_by": w.exported_by}
        w.exported_at, w.exported_by = stamp, user.email
        db.add(AuditLog(business_date=current_business_date(db), actor=user.email, actor_role=user.role, entity_type="work_item",
                        entity_id=w.entry_id, action="EXPORTED_TO_EXCEL",
                        details={"before": before, "after": {"exported_at": str(stamp), "exported_by": user.email}}))
    db.commit()
    return len(rows)
