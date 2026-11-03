"""Demo Control (M11): the reset point, "Reset demo", sending live-set samples, moving the business date.

RESET POINT = schema `demo_reset`: a copy of every ar.* table (except the job queue) and of sap.bsid / sap.bsad, taken ONCE after the
history was built (scripts.build_history does it at its end; take_reset_point can be run again on purpose).
RESET DEMO = TRUNCATE ar.* and refill it from the copy. That brings back everything the demo changed, because all of it lives in ar.*:
work-item statuses and comments, the exported-cases list (confirmed_at / exported_at), PTP statuses and alert flags, outbound e-mails,
audit entries, the list of samples already sent, and the business date (ar.rule_config). The job queue is emptied.
Sequences are NOT moved back (entry numbers and e-mail numbers are never reused, so old attachment files cannot clash with new ones).
A column that was added after the reset point was taken gets its default; a column that was dropped is ignored.
"""
import json
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.auth import CurrentUser
from app.businessdate import current_business_date
from app.config import get_settings
from app.models.ar import AuditLog, DemoSampleSent, Job, RuleConfig

SCHEMA = "demo_reset"
SAP_TABLES = ("bsid", "bsad")
NO_COPY = ("job",)          # the queue is emptied by a reset, never restored
RESET_LOCK = 7310011        # PostgreSQL advisory lock: one reset (or reset point) at a time
RUNNING_FRESH = timedelta(minutes=15)  # a RUNNING job older than this belongs to a crashed worker


class DemoError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


# --------------------------------------------------------------------------- catalog helpers
def _ar_tables(db: Session) -> list[str]:
    return [r[0] for r in db.execute(text("select tablename from pg_tables where schemaname = 'ar' order by 1"))]


def _fk_order(db: Session, tables: list[str]) -> list[str]:
    """Parents before children (foreign keys inside ar). Self references stay with their table (rows are inserted in id order)."""
    deps: dict[str, set[str]] = {t: set() for t in tables}
    for child, parent in db.execute(text(
            "select c.relname, p.relname from pg_constraint k join pg_class c on c.oid = k.conrelid "
            "join pg_class p on p.oid = k.confrelid join pg_namespace n on n.oid = c.relnamespace "
            "join pg_namespace pn on pn.oid = p.relnamespace where k.contype = 'f' and n.nspname = 'ar' and pn.nspname = 'ar'")):
        if child != parent and child in deps and parent in deps:
            deps[child].add(parent)
    ordered: list[str] = []
    while deps:
        ready = sorted(t for t, d in deps.items() if d <= set(ordered))
        if not ready:
            raise DemoError(500, f"Tables in a foreign-key cycle: {sorted(deps)}")
        for t in ready:
            ordered.append(t)
            del deps[t]
    return ordered


def _columns(db: Session, schema: str, table: str) -> list[str]:
    return [r[0] for r in db.execute(text("select column_name from information_schema.columns where table_schema = :s and table_name = :t "
                                          "order by ordinal_position"), {"s": schema, "t": table})]


def _copy_name(schema: str, table: str) -> str:
    return f"{schema}__{table}"


def _sequences(db: Session) -> dict[str, dict]:
    out = {}
    for (name,) in db.execute(text("select sequence_name from information_schema.sequences where sequence_schema = 'ar'")):
        last, called = db.execute(text(f'select last_value, is_called from ar."{name}"')).one()
        out[name] = {"last_value": int(last), "is_called": bool(called)}
    return out


def _sap_fingerprint(db: Session) -> dict:
    return {t: [int(x or 0) for x in db.execute(text(f"select count(*), coalesce(sum(id), 0) from sap.{t}")).one()]
            + [str(db.execute(text(f"select coalesce(sum(wrbtr), 0) from sap.{t}")).scalar())] for t in SAP_TABLES}


# --------------------------------------------------------------------------- reset point
def reset_point_info(db: Session) -> dict | None:
    exists = db.execute(text("select to_regclass('demo_reset.meta')")).scalar()
    if not exists:
        return None
    row = db.execute(text("select value from demo_reset.meta where key = 'reset_point'")).first()
    return row[0] if row else None


def take_reset_point(db: Session, actor: str = "system") -> dict:
    """Copy ar.* (not the job queue) and sap.bsid / sap.bsad into demo_reset. Replaces an older reset point."""
    if not db.execute(text("select pg_try_advisory_xact_lock(:k)"), {"k": RESET_LOCK}).scalar():
        raise DemoError(409, "A reset or a reset point is being made right now - try again in a moment.")
    db.execute(text(f"create schema if not exists {SCHEMA}"))
    for (name,) in db.execute(text("select tablename from pg_tables where schemaname = :s"), {"s": SCHEMA}).all():
        db.execute(text(f'drop table if exists {SCHEMA}."{name}"'))
    counts = {}
    for t in _ar_tables(db):
        if t in NO_COPY:
            continue
        db.execute(text(f'create table {SCHEMA}."{_copy_name("ar", t)}" as table ar."{t}"'))
        counts[f"ar.{t}"] = db.execute(text(f'select count(*) from ar."{t}"')).scalar()
    for t in SAP_TABLES:
        db.execute(text(f'create table {SCHEMA}."{_copy_name("sap", t)}" as table sap."{t}"'))
        counts[f"sap.{t}"] = db.execute(text(f'select count(*) from sap."{t}"')).scalar()
    info = {"taken_at": datetime.now(timezone.utc).isoformat(), "taken_by": actor,
            "alembic_revision": db.execute(text("select version_num from alembic_version")).scalar(),
            "business_date": current_business_date(db).isoformat(), "counts": counts, "sequences": _sequences(db),
            "sap_fingerprint": _sap_fingerprint(db)}
    db.execute(text(f"create table {SCHEMA}.meta (key text primary key, value jsonb not null)"))
    db.execute(text(f"insert into {SCHEMA}.meta (key, value) values ('reset_point', cast(:v as jsonb))"), {"v": json.dumps(info)})
    db.add(AuditLog(actor=actor, entity_type="demo", entity_id="reset_point", action="DEMO_RESET_POINT_TAKEN",
                    details={"counts": counts, "business_date": info["business_date"]}))
    db.flush()
    return info


def restore_reset_point(db: Session, user: CurrentUser) -> dict:
    """Reset demo: bring every ar.* table back to the reset point (one transaction: all or nothing)."""
    info = reset_point_info(db)
    if info is None:
        raise DemoError(409, "There is no reset point yet. It is created after the history has been built (scripts.build_history).")
    if not db.execute(text("select pg_try_advisory_xact_lock(:k)"), {"k": RESET_LOCK}).scalar():
        raise DemoError(409, "A reset is already running.")
    busy = db.scalar(select(func.count()).select_from(Job).where(
        Job.status == "RUNNING", Job.started_at > datetime.now(timezone.utc) - RUNNING_FRESH))
    if busy:
        raise DemoError(409, f"{busy} background job(s) are running right now - wait a minute and try again.")

    tables = [t for t in _ar_tables(db)]
    db.execute(text("truncate " + ", ".join(f'ar."{t}"' for t in tables) + " cascade"))
    restored: dict[str, int] = {}
    for t in _fk_order(db, [t for t in tables if t not in NO_COPY]):
        copy = _copy_name("ar", t)
        if not db.execute(text("select to_regclass(:n)"), {"n": f'{SCHEMA}."{copy}"'}).scalar():
            continue  # a table added after the reset point: stays empty
        cols = [c for c in _columns(db, "ar", t) if c in set(_columns(db, SCHEMA, copy))]
        names = ", ".join(f'"{c}"' for c in cols)
        order = ' order by "id"' if "id" in cols else ""
        db.execute(text(f'insert into ar."{t}" ({names}) select {names} from {SCHEMA}."{copy}"{order}'))
        restored[t] = db.execute(text(f'select count(*) from ar."{t}"')).scalar()

    for name, snap in (info.get("sequences") or {}).items():  # never move a sequence back: numbers are not reused
        if not db.execute(text("select to_regclass(:n)"), {"n": f'ar."{name}"'}).scalar():
            continue
        cur_last, cur_called = db.execute(text(f'select last_value, is_called from ar."{name}"')).one()
        if snap["is_called"] or cur_called:
            db.execute(text("select setval(:n, :v, true)"), {"n": f"ar.{name}", "v": max(int(cur_last), snap["last_value"])})

    sap_restored = _sap_fingerprint(db) != info.get("sap_fingerprint")
    if sap_restored:  # SAP data is never changed by the app; this only repairs it if somebody did
        for t in SAP_TABLES:
            cols = ", ".join(f'"{c}"' for c in _columns(db, "sap", t))
            db.execute(text(f'truncate sap."{t}"'))
            db.execute(text(f'insert into sap."{t}" ({cols}) select {cols} from {SCHEMA}."{_copy_name("sap", t)}"'))

    db.add(AuditLog(business_date=current_business_date(db), actor=user.email, actor_role=user.role, entity_type="demo",
                    entity_id="reset", action="DEMO_RESET",
                    details={"reset_point_taken_at": info.get("taken_at"), "restored_rows": restored, "sap_restored": sap_restored,
                             "stale_reset_point": info.get("alembic_revision") != db.execute(text("select version_num from alembic_version")).scalar()}))
    db.flush()
    return {"reset_point_taken_at": info.get("taken_at"), "business_date": current_business_date(db).isoformat(),
            "restored_rows": restored, "sap_restored": sap_restored}


# --------------------------------------------------------------------------- Demo Control state
_catalog: dict[str, dict] = {}


def _describe(code: str) -> dict:
    if code not in _catalog:
        from app.gmail import sample_library

        s = sample_library.get_library().load(code)
        _catalog[code] = {"code": code, "scenario": code.split("-")[0], "from": s.headers.get("from"), "subject": s.headers.get("subject"),
                          "attachments": [a.name for a in s.attachments]}
    return _catalog[code]


def live_samples(db: Session) -> list[dict]:
    from app.gmail import sample_library

    sent: dict[str, list] = {}
    for row in db.scalars(select(DemoSampleSent).order_by(DemoSampleSent.id)):
        sent.setdefault(row.code, []).append(row)
    out = []
    for code in sample_library.live_set():
        try:
            d = dict(_describe(code))
        except Exception:  # a sample that cannot be read must not hide the others
            d = {"code": code, "scenario": code.split("-")[0], "from": None, "subject": "(sample file not found)", "attachments": []}
        rows = sent.get(code, [])
        d.update(sent_count=len(rows), last_sent_at=rows[-1].sent_at if rows else None, last_sent_by=rows[-1].sent_by if rows else None)
        out.append(d)
    return out


def state(db: Session) -> dict:
    s = get_settings()
    try:
        live, live_error = live_samples(db), None
    except FileNotFoundError as exc:
        live, live_error = [], str(exc)
    rp = reset_point_info(db)
    return {"business_date": current_business_date(db), "default_business_date": s.business_date,
            "reset_point": {k: rp[k] for k in ("taken_at", "taken_by", "business_date", "counts")} if rp else None,
            "live_set": live, "live_set_error": live_error,
            "sent_total": db.scalar(select(func.count()).select_from(DemoSampleSent)) or 0}


# --------------------------------------------------------------------------- actions
def send_sample(db: Session, user: CurrentUser, code: str, service=None) -> dict:
    """Put one live-set sample into the Gmail inbox with the customer as sender (the worker reads it like real mail)."""
    from app.gmail import sample_library
    from app.gmail.sample_sender import build_message, import_to_inbox

    if code not in sample_library.live_set():
        raise DemoError(422, f"{code} is not in the live set.")
    try:
        sample = sample_library.get_library().load(code)
    except FileNotFoundError as exc:
        raise DemoError(404, str(exc)) from exc
    if service is None:
        from app.gmail.client import GmailNotConfigured, build_service

        try:
            service = build_service()
        except GmailNotConfigured as exc:
            raise DemoError(409, str(exc)) from exc
    result = import_to_inbox(service, build_message(sample))
    db.add(DemoSampleSent(code=code, sent_by=user.email, gmail_id=result.get("id")))
    db.add(AuditLog(business_date=current_business_date(db), actor=user.email, actor_role=user.role, entity_type="demo", entity_id=code,
                    action="DEMO_SAMPLE_SENT", details={"gmail_id": result.get("id"), "from": sample.headers.get("from"),
                                                        "subject": sample.headers.get("subject")}))
    db.flush()
    return {"code": code, "gmail_id": result.get("id"), "from": sample.headers.get("from"), "subject": sample.headers.get("subject")}


def set_business_date(db: Session, user: CurrentUser, *, day: date | None = None, add_days: int | None = None) -> dict:
    """Move the demo business date (all rules use it), then check the promises to pay at once so the PTP Tracker and the alert
    e-mails follow the new date."""
    from app import ptp

    before = current_business_date(db)
    if (day is None) == (add_days is None):
        raise DemoError(422, "Give either a date or a number of days to add.")
    new = day if day is not None else before + timedelta(days=add_days)
    if not date(2020, 1, 1) <= new <= date(2035, 12, 31):
        raise DemoError(422, "That business date is out of range.")
    row = db.get(RuleConfig, "business_date")
    if row is None:
        db.add(RuleConfig(key="business_date", value={"date": new.isoformat()}, description="The demo business date used by all rules."))
    else:
        row.value = {"date": new.isoformat()}
    db.add(AuditLog(business_date=new, actor=user.email, actor_role=user.role, entity_type="demo", entity_id="business_date",
                    action="DEMO_BUSINESS_DATE", details={"before": before.isoformat(), "after": new.isoformat()}))
    db.flush()
    result = ptp.evaluate(db, actor=user.email, actor_role=user.role)
    return {"business_date": new, "before": before, "ptp": {"checked": result.checked, "changed": result.changed,
                                                          "alerts": result.alerts, "escalations": result.escalations}}
