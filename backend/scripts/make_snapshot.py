"""Build the data of the demo (snapshot) edition in a CLEAN database (M15).

    set DATABASE_NAME=ar_snapshot  (PowerShell: $env:DATABASE_NAME = "ar_snapshot")   # same server, user and password as DATABASE_URL
    python -m scripts.make_snapshot            # migrations, SAP + users, 3 months of history, the 47 live-set e-mails left open
    python -m scripts.make_snapshot --export   # ... and then export + check (scripts.export_snapshot / scripts.check_snapshot)

Refuses to run against the normal database (ar_demo): the snapshot must contain nothing but the samples. Safe to run again: every step
skips what exists. The business date is the default one (2026-10-28).
"""
import argparse
import subprocess
import sys
from pathlib import Path

from app.config import get_settings

ROOT = Path(__file__).resolve().parents[1]


def run(*module_args: str) -> None:
    print(f"\n=== python -m {' '.join(module_args)}")
    r = subprocess.run([sys.executable, "-m", *module_args], cwd=ROOT)
    if r.returncode != 0:
        raise SystemExit(f"Step failed: {' '.join(module_args)} (exit {r.returncode})")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--export", action="store_true", help="export and check the snapshot at the end")
    ap.add_argument("--fresh", action="store_true", help="first empty the ar.* tables of this clean database (never of ar_demo), then build")
    args = ap.parse_args(argv)
    s = get_settings()
    if not s.database_name or s.database_name == "ar_demo":
        print("Refusing: set DATABASE_NAME=ar_snapshot first (a clean database), never the normal one.")
        return 1
    print(f"Database: {s.database_url.split('@')[-1]}")
    if args.fresh:
        from sqlalchemy import text

        from app.db import SessionLocal

        with SessionLocal.begin() as db:
            names = [r[0] for r in db.execute(text("select tablename from pg_tables where schemaname = 'ar'"))]
            if names:
                db.execute(text("truncate " + ", ".join(f'ar."{n}"' for n in names) + " restart identity cascade"))
            for (seq,) in db.execute(text("select sequence_name from information_schema.sequences where sequence_schema = 'ar'")).all():
                db.execute(text(f'alter sequence ar."{seq}" restart with 1'))
        print("ar.* emptied (fresh start)")

    run("alembic", "upgrade", "head")
    run("scripts.load_reference")
    run("scripts.seed_app")
    run("scripts.build_history", "--no-snapshot")

    from app import history, ptp
    from app.businessdate import current_business_date
    from app.db import SessionLocal
    from app.gmail import sample_library

    db = SessionLocal()
    lib, bd = sample_library.get_library(), current_business_date(SessionLocal())
    live = sample_library.live_set(lib)
    stats = history.build_emails(db, live, lib, bd, source="sample", day_of=history.live_set_days(live, bd), shift=False)
    print(f"\nLive set: {stats.built} built, {stats.skipped} already there, {len(stats.failed)} failed")
    for f in stats.failed:
        print("  FAILED", f)
    if len(stats.failed) > 3:
        return 1
    print(ptp.evaluate(db, actor="make_snapshot").line())
    if args.export:
        run("scripts.export_snapshot")
        run("scripts.check_snapshot")
    return 0


if __name__ == "__main__":
    sys.exit(main())
