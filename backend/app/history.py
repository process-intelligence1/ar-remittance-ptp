"""History for the demo (M11): about 190 sample e-mails spread over the 3 months before the business date, processed by the normal
pipeline, then worked by the four demo users so that every invoice has an action trail.

Everything here is deterministic (seeded by sample code and line number), resumable (an e-mail that was already built, and a
row that already has a user action, are skipped) and additive (it never deletes anything and takes new entry / e-mail numbers
from the normal sequences). History e-mails get source = 'history': the worker never picks them up, their promises are flagged
without any e-mail, and the clarifications they contain are stored as already sent. Nothing here sends mail or touches Gmail.
"""
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import date, datetime, time as dtime, timedelta, timezone

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app import actions, outbound
from app.api.auth import CurrentUser
from app.businessdate import current_business_date, override_business_date
from app.models.ar import AppUser, AuditLog, EmailMessage, OutboundMessage, PtpCommitment, WorkItem

log = logging.getLogger("history")
BUILD_LOCK = 7310012
SEED = "ar-demo-history-1"
MONTHS = 3


# --------------------------------------------------------------------------- dates
def business_days(start: date, end: date) -> list[date]:
    days, d = [], start
    while d <= end:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def spread_dates(n: int, business_date: date) -> list[date]:
    """n dates (non-decreasing, weekdays only) from three months before the business date up to the day before it."""
    start = business_date - timedelta(days=MONTHS * 30 + 2)
    days = business_days(start, business_date - timedelta(days=1))
    return [days[min(len(days) - 1, i * len(days) // max(n, 1))] for i in range(n)]


def received_at(day: date, key: str) -> datetime:
    r = random.Random(f"{SEED}:time:{key}")
    return datetime.combine(day, dtime(r.randint(7, 16), r.randint(0, 59), r.randint(0, 59)), tzinfo=timezone.utc)


# --------------------------------------------------------------------------- step 1: the e-mails
def sample_day(sample) -> date:
    from app.gmail.sample_sender import _sample_date

    return _sample_date(sample.headers.get("date")).date()


def shift_dates(db: Session, email: EmailMessage, days: int) -> None:
    """The sample texts carry absolute dates written for "now". The e-mail was moved into the past, so the dates that belong to it
    (promise date, payment date) move with it - a promise made in August falls due in the weeks after August, not in November."""
    if not days:
        return
    delta = timedelta(days=days)
    db.execute(update(WorkItem).where(WorkItem.email_id == email.id).values(
        payment_date=WorkItem.payment_date + delta, promise_date=WorkItem.promise_date + delta))
    ids = select(WorkItem.id).where(WorkItem.email_id == email.id)
    db.execute(update(PtpCommitment).where(PtpCommitment.work_item_id.in_(ids)).values(promise_date=PtpCommitment.promise_date + delta))



@dataclass
class BuildStats:
    built: int = 0
    skipped: int = 0
    failed: list[str] = field(default_factory=list)
    seconds: float = 0.0
    out_of_time: bool = False


def build_emails(db: Session, codes: list[str], library, business_date: date, *, time_budget_s: float | None = None,
                 limit: int | None = None, process=None, storage=None, source: str = "history",
                 day_of: dict[str, date] | None = None, shift: bool = True) -> BuildStats:
    """Store and process each sample as an e-mail dated in the past (source 'history'; M15 also builds the live set as source
    'sample' dated in the last days before the business date). Already built samples are skipped."""
    from app.gmail.poller import store_email
    from app.gmail.sample_sender import build_message

    if process is None:
        from app.pipeline import process_email as process
    stats, started = BuildStats(), time.monotonic()
    dates = day_of or dict(zip(codes, spread_dates(len(codes), business_date)))
    have = set(db.scalars(select(EmailMessage.sample_code).where(EmailMessage.source == source)))
    for i, code in enumerate(codes, start=1):
        if code in have:
            stats.skipped += 1
            continue
        if limit is not None and stats.built >= limit:
            break
        if time_budget_s is not None and time.monotonic() - started > time_budget_s:
            stats.out_of_time = True
            break
        t0 = time.monotonic()
        try:
            sample = library.load(code)
            when = received_at(dates[code], code)
            raw = build_message(sample, now=when).as_bytes()
            with override_business_date(dates[code]):
                email = store_email(db, raw, storage=storage, source=source)
                db.commit()
                process(db, email, last_attempt=True)
            if shift:
                shift_dates(db, email, (dates[code] - sample_day(sample)).days)
                db.commit()
            stats.built += 1
            log.info("[%d/%d] %s -> %s %s (%.1f s)", i, len(codes), code, email.email_ref, dates[code], time.monotonic() - t0)
        except Exception as exc:  # one broken sample must not stop the build
            db.rollback()
            stats.failed.append(f"{code}: {type(exc).__name__}: {exc}")
            log.error("[%d/%d] %s FAILED: %s", i, len(codes), code, exc)
    stats.seconds = time.monotonic() - started
    return stats


def last_days(business_date: date, n: int = 3) -> list[date]:
    """The last n working days up to and including the business date."""
    return business_days(business_date - timedelta(days=n + 6), business_date)[-n:]


def live_set_days(codes: list[str], business_date: date) -> dict[str, date]:
    days = last_days(business_date)
    return {c: days[i * len(days) // max(len(codes), 1)] for i, c in enumerate(codes)}


# --------------------------------------------------------------------------- step 2: the users work on the rows
COMMENTS = {
    "CONFIRM_ADD_EXCEL": ["Checked against the remittance advice.", "Amount and invoice agree - added to the posting file.", "OK to post.", None, None],
    "REJECT": ["Not our customer - rejected.", "Cannot be matched to an open item.", "Payment belongs to another entity.", "Unreadable advice, rejected."],
    "ESCALATE_TO_SUPERVISOR": ["Large difference - please decide.", "Customer disputes the invoice.", "Needs a supervisor decision."],
    "CLOSE_AS_DUPLICATE": ["Same advice received twice.", "Duplicate of the earlier e-mail.", None],
}


@dataclass
class ActionStats:
    rows: int = 0
    actions: int = 0
    skipped: int = 0
    exported: int = 0
    by_action: dict = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


class Player:
    """Works one row at a time. All timestamps are in the past (after the e-mail, never after the business date)."""

    def __init__(self, db: Session, business_date: date, users: dict[str, CurrentUser], stats: ActionStats):
        self.db, self.bd, self.users, self.stats = db, business_date, users, stats
        self.ctx = actions.Context(db, history=True)
        self.end = datetime.combine(business_date, dtime(17, 0), tzinfo=timezone.utc)

    # -- one action, then stamp its audit entry and the row with a past time
    def do(self, rng: random.Random, ts: datetime, role: str, w: WorkItem, action: str, **kw) -> datetime:
        ts = min(ts + timedelta(hours=rng.uniform(2, 30)), self.end)
        comment = kw.pop("comment", None) or (rng.choice(COMMENTS[action]) if action in COMMENTS else None)
        self.db.refresh(w)
        user = self.users[role]
        actions.apply_action(self.ctx, user, w, action, version=w.row_version, comment=comment, commit=False, **kw)
        self.stats.actions += 1
        self.stats.by_action[action] = self.stats.by_action.get(action, 0) + 1
        self.stamp(w, action, ts)
        return ts

    def stamp(self, w: WorkItem, action: str, ts: datetime) -> None:
        db = self.db
        last = db.scalar(select(AuditLog.id).where(AuditLog.entity_type == "work_item", AuditLog.entity_id == w.entry_id,
                                                   AuditLog.action == action).order_by(AuditLog.id.desc()).limit(1))
        if last:
            db.execute(update(AuditLog).where(AuditLog.id == last).values(occurred_at=ts, business_date=ts.date()))
        values = {"updated_at": ts}
        db.refresh(w)
        if w.confirmed_at is not None and action == "CONFIRM_ADD_EXCEL":
            values["confirmed_at"] = ts
        if w.resolved_at is not None and action in ("CONFIRM_ADD_EXCEL", "REJECT", "CLOSE_AS_DUPLICATE"):
            values["resolved_at"] = ts
        db.execute(update(WorkItem).where(WorkItem.id == w.id).values(**values))  # core update: keeps row_version
        if action == "REQUEST_CLARIFICATION":
            db.execute(update(OutboundMessage).where(OutboundMessage.work_item_id == w.id, OutboundMessage.status == "SENT")
                       .values(created_at=ts, sent_at=ts))
        db.flush()
        db.refresh(w)

    def customer_replies(self, rng: random.Random, ts: datetime, w: WorkItem) -> datetime:
        """The customer answers a clarification: the row is back in review (what outbound.attach_reply does for a real reply)."""
        ts = min(ts + timedelta(hours=rng.uniform(6, 60)), self.end)
        self.db.refresh(w)
        w.status = "PENDING_REVIEW"
        self.db.add(AuditLog(business_date=ts.date(), actor="system", entity_type="work_item", entity_id=w.entry_id, action="CUSTOMER_REPLIED",
                             occurred_at=ts, details={"before": {"status": "AWAITING_CUSTOMER"}, "after": {"status": "PENDING_REVIEW"}}))
        self.db.flush()
        self.db.execute(update(WorkItem).where(WorkItem.id == w.id).values(updated_at=ts))
        self.db.refresh(w)
        return ts

    def clarify(self, rng, ts, role, w):
        from app.outbound import render_clarification

        e = self.db.get(EmailMessage, w.email_id)
        draft = render_clarification(self.db, w, e)
        return self.do(rng, ts, role, w, "REQUEST_CLARIFICATION", email={"subject": draft["subject"], "body": draft["body"]})

    def try_confirm(self, rng, ts, role, w) -> datetime:
        """Confirm; a row that cannot be confirmed (incomplete) is rejected instead - like an analyst would."""
        try:
            return self.do(rng, ts, role, w, "CONFIRM_ADD_EXCEL")
        except actions.ActionError:  # refused before anything was changed (apply_action checks first), so no rollback
            return self.try_reject(rng, ts, role, w)

    def try_reject(self, rng, ts, role, w) -> datetime:
        try:
            return self.do(rng, ts, role, w, "REJECT")
        except actions.ActionError as exc:
            self.stats.problems.append(f"{w.entry_id}: {exc.message}")
            return ts

    def allowed(self, role: str, w: WorkItem) -> list[str]:
        from app.permissions import allowed_actions

        return allowed_actions(self.users[role].role, w.decision, w.status, w.assigned_role, bool(w.resolved_at))

    def has_user_action(self, w: WorkItem) -> bool:
        return bool(self.db.scalar(select(AuditLog.id).where(
            AuditLog.entity_type == "work_item", AuditLog.entity_id == w.entry_id, AuditLog.actor != "system",
            AuditLog.action != "EXPORTED_TO_EXCEL").limit(1)))

    # -- the rules by decision
    def work(self, w: WorkItem, e: EmailMessage) -> None:
        rng = random.Random(f"{SEED}:{e.sample_code}:{w.line_no}")
        ts = e.received_at or datetime.combine(self.bd - timedelta(days=30), dtime(9, 0), tzinfo=timezone.utc)
        analyst = "AR_ANALYST"
        worker = "COLLECTIONS_ANALYST" if w.line_type == "PTP" else "CASH_APPLICATION"
        d = w.decision
        try:
            self._plan(rng, ts, analyst, worker, d, w, e)
        except actions.ActionError as exc:  # refused before anything changed: the trail check below finds another way
            self.stats.problems.append(f"{w.entry_id}: {exc.message}")
        self.finish_row(rng, ts, analyst, worker, w)

    def _plan(self, rng, ts, analyst, worker, d, w, e):
        if d == "AUTO_PROCESS":
            ts = self.try_confirm(rng, ts, worker, w)
        elif d == "DUPLICATE":
            if rng.random() < 0.75 or not w.duplicate_of_id:
                self.do(rng, ts, analyst, w, "CLOSE_AS_DUPLICATE")
            else:
                ts = self.do(rng, ts, analyst, w, "MARK_NON_DUPLICATE")
                ts = self.try_confirm(rng, ts, analyst, w) if w.decision != "DUPLICATE" else ts
        elif d == "MANUAL_REVIEW" and w.match_level == "NEAR" and w.bsid_id and rng.random() < 0.6:
            xb = self.db.execute(text("select xblnr from sap.bsid where id = :i"), {"i": w.bsid_id}).scalar()
            if xb:  # the analyst corrects the OCR misread; the row is scored again
                ts = self.do(rng, ts, analyst, w, "ADD_UPDATE_DETAILS", details={"invoice_ref": xb}, comment="Corrected OCR misread of the invoice number.")
                ts = self.try_confirm(rng, ts, analyst, w)
            else:
                ts = self.try_confirm(rng, ts, analyst, w)
        else:
            roll = rng.random()
            plan = {"MANUAL_REVIEW": [(0.62, "confirm"), (0.84, "clarify"), (1.0, "reject")],
                    "EXCEPTION": [(0.15, "confirm"), (0.55, "clarify"), (1.0, "reject")],
                    "MANUAL_INVESTIGATION": [(0.15, "confirm"), (0.40, "clarify"), (0.55, "reject"), (1.0, "escalate")]}.get(d, [(1.0, "confirm")])
            choice = next(c for p, c in plan if roll < p)
            can = self.allowed(analyst, w)  # the Knowledge Base decides what is offered; fall back like an analyst would
            if choice == "escalate" and "ESCALATE_TO_SUPERVISOR" not in can:
                choice = "clarify"
            if choice == "clarify" and "REQUEST_CLARIFICATION" not in can:
                choice = "reject"
            recent = (self.bd - ts.date()).days <= 7
            if choice == "confirm":
                ts = self.try_confirm(rng, ts, analyst, w)
            elif choice == "reject":
                ts = self.try_reject(rng, ts, analyst, w)
            elif choice == "clarify":
                ts = self.clarify(rng, ts, analyst, w)
                if not recent and rng.random() < 0.7:  # the customer answers, the analyst finishes the row
                    ts = self.customer_replies(rng, ts, w)
                    ts = self.try_confirm(rng, ts, analyst, w) if rng.random() < 0.65 else self.try_reject(rng, ts, analyst, w)
            else:  # escalate
                ts = self.do(rng, ts, analyst, w, "ESCALATE_TO_SUPERVISOR")
                if not recent and rng.random() < 0.8:
                    ts = self.try_confirm(rng, ts, "AR_SUPERVISOR", w) if rng.random() < 0.6 else self.try_reject(rng, ts, "AR_SUPERVISOR", w)

    def finish_row(self, rng, ts, analyst, worker, w):
        self.db.refresh(w)
        if not self.has_user_action(w):  # every invoice gets a trail, whatever the rules offered
            for fallback in ("REJECT", "REQUEST_CLARIFICATION", "CLOSE_AS_DUPLICATE", "CONFIRM_ADD_EXCEL"):
                if fallback in self.allowed(analyst, w) or fallback in self.allowed(worker, w):
                    role = analyst if fallback in self.allowed(analyst, w) else worker
                    if fallback == "REQUEST_CLARIFICATION":
                        self.clarify(rng, ts, role, w)
                    else:
                        self.do(rng, ts, role, w, fallback)
                    break
        # some confirmed rows were downloaded to Excel later
        self.db.refresh(w)
        if w.status == "CONFIRMED" and w.exported_at is None and rng.random() < 0.7:
            when = min((w.confirmed_at or ts) + timedelta(days=rng.randint(1, 4), hours=rng.randint(0, 6)), self.end)
            who = self.users[worker].email
            self.db.execute(update(WorkItem).where(WorkItem.id == w.id).values(exported_at=when, exported_by=who))
            self.db.add(AuditLog(business_date=when.date(), actor=who, actor_role=self.users[worker].role, entity_type="work_item",
                                 entity_id=w.entry_id, action="EXPORTED_TO_EXCEL", occurred_at=when,
                                 details={"before": {"exported_at": None}, "after": {"exported_at": when.isoformat(), "exported_by": who}}))
            self.stats.exported += 1
            self.db.flush()


def load_users(db: Session) -> dict[str, CurrentUser]:
    users = {u.role: CurrentUser(email=u.email, name=u.display_name, role=u.role)
             for u in db.scalars(select(AppUser).where(AppUser.active.is_(True)).order_by(AppUser.id))}
    missing = {"AR_ANALYST", "CASH_APPLICATION", "COLLECTIONS_ANALYST", "AR_SUPERVISOR"} - set(users)
    if missing:
        raise RuntimeError(f"Demo users missing: {sorted(missing)} (run scripts.seed_app)")
    return users


def play_actions(db: Session, business_date: date, *, time_budget_s: float | None = None) -> ActionStats:
    """Every in-scope row of the history that has no user action yet gets its trail. Resumable."""
    stats, started = ActionStats(), time.monotonic()
    users = load_users(db)
    acted = set(db.scalars(select(AuditLog.entity_id).where(AuditLog.entity_type == "work_item", AuditLog.actor != "system",
                                                           AuditLog.action != "EXPORTED_TO_EXCEL")))
    rows = db.execute(select(WorkItem, EmailMessage).join(EmailMessage, EmailMessage.id == WorkItem.email_id)
                      .where(EmailMessage.source == "history", WorkItem.status != "IGNORED", WorkItem.decision != "OUT_OF_SCOPE")
                      .order_by(EmailMessage.received_at, WorkItem.line_no, WorkItem.id)).all()
    player = Player(db, business_date, users, stats)
    for w, e in rows:
        if w.entry_id in acted:
            stats.skipped += 1
            continue
        if time_budget_s is not None and time.monotonic() - started > time_budget_s:
            stats.problems.append("out of time - run again to continue")
            break
        try:
            player.work(w, e)
            db.commit()
            stats.rows += 1
        except Exception as exc:
            db.rollback()
            stats.problems.append(f"{w.entry_id}: {type(exc).__name__}: {exc}")
            log.error("%s: %s", w.entry_id, exc)
    return stats


# --------------------------------------------------------------------------- step 3: report
def report(db: Session) -> dict:
    rows = db.execute(text("select w.status, w.decision, count(*) from ar.work_item w join ar.email_message e on e.id = w.email_id "
                           "where e.source = 'history' group by 1, 2 order by 1, 2")).all()
    no_trail = db.scalar(text("select count(*) from ar.work_item w join ar.email_message e on e.id = w.email_id where e.source = 'history' "
                              "and w.status <> 'IGNORED' and w.decision <> 'OUT_OF_SCOPE' and not exists (select 1 from ar.audit_log a "
                              "where a.entity_type = 'work_item' and a.entity_id = w.entry_id and a.actor <> 'system' and a.action <> 'EXPORTED_TO_EXCEL')"))
    return {"emails": db.scalar(text("select count(*) from ar.email_message where source = 'history'")),
            "work_items": [(s, d, n) for s, d, n in rows], "rows_without_user_action": no_trail,
            "promises": db.execute(text("select p.status, count(*) from ar.ptp_commitment p join ar.work_item w on w.id = p.work_item_id "
                                        "join ar.email_message e on e.id = w.email_id where e.source = 'history' group by 1 order by 1")).all(),
            "exported": db.scalar(text("select count(*) from ar.work_item w join ar.email_message e on e.id = w.email_id "
                                       "where e.source = 'history' and w.exported_at is not null"))}
