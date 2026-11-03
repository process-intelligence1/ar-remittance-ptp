"""Build the demo history (M11): the history samples as e-mails of the last 3 months, worked by the four demo users, then the reset point.

    python -m scripts.build_history                  # laptop (local database, local samples)
    python -m scripts.build_history --limit 20 --no-snapshot --no-actions     # a quick trial
    python -m scripts.build_history --plan           # only show what it would do

In Azure it runs as the one-off Container Apps job "ar-history" (worker image, 1 hour): the samples are read from the Blob
container, the database and files are the ones the app already uses. It is additive and can be started again: finished
e-mails and rows are skipped. The reset point (schema demo_reset) is taken ONLY after everything has been built; an unfinished
run (out of time, too many failures) ends with exit code 3 and no reset point.
"""
import argparse
import logging
import sys

from sqlalchemy import text

from app import demo, history, ptp
from app.businessdate import current_business_date
from app.db import SessionLocal
from app.gmail import sample_library

MAX_FAILURES = 3  # more failed samples than this = something is wrong: no reset point


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, help="build at most this many new e-mails (trial)")
    ap.add_argument("--time-budget", type=float, default=3200, help="seconds before it stops cleanly (default 3200: the job runs 3600)")
    ap.add_argument("--no-actions", action="store_true", help="only build the e-mails")
    ap.add_argument("--no-snapshot", action="store_true", help="do not take the reset point at the end")
    ap.add_argument("--plan", action="store_true", help="show the plan and stop")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    db = SessionLocal()
    lib = sample_library.get_library()
    codes = sample_library.history_set(lib)
    bd = current_business_date(db)
    print(f"History samples: {len(codes)} | business date {bd} | dates {history.spread_dates(len(codes), bd)[0]} .. {history.spread_dates(len(codes), bd)[-1]}")
    if args.plan:
        return 0
    if not db.execute(text("select pg_try_advisory_lock(:k)"), {"k": history.BUILD_LOCK}).scalar():
        print("Another history build is running - nothing done.")
        return 1

    stats = history.build_emails(db, codes, lib, bd, time_budget_s=args.time_budget, limit=args.limit)
    print(f"E-mails: {stats.built} built, {stats.skipped} already there, {len(stats.failed)} failed, {stats.seconds:.0f} s"
          + (" (OUT OF TIME - run again)" if stats.out_of_time else ""))
    for f in stats.failed:
        print("  FAILED", f)
    complete = not stats.out_of_time and args.limit is None and len(stats.failed) <= MAX_FAILURES

    if not args.no_actions:
        remaining = max(60.0, args.time_budget - stats.seconds)
        a = history.play_actions(db, bd, time_budget_s=remaining)
        print(f"Actions: {a.actions} on {a.rows} rows ({a.skipped} rows already had a trail), {a.exported} exported; by action: {a.by_action}")
        for p in a.problems[:10]:
            print("  PROBLEM", p)
        complete = complete and not any("out of time" in p for p in a.problems)
        r = ptp.evaluate(db, actor="build_history")  # history promises are flagged, never e-mailed
        print(f"Promises: {r.line()} -> {r.counts}")

    rep = history.report(db)
    print(f"Report: {rep['emails']} history e-mails | rows without a user action: {rep['rows_without_user_action']} | exported: {rep['exported']}")
    print("  work items:", rep["work_items"])
    print("  promises:", rep["promises"])
    complete = complete and (args.no_actions or rep["rows_without_user_action"] == 0)

    if complete and not args.no_snapshot and not args.no_actions:
        info = demo.take_reset_point(db, "build_history")
        db.commit()
        print(f"RESET POINT taken: {info['counts']['ar.work_item']} work items, {info['counts']['ar.email_message']} e-mails, business date {info['business_date']}")
    elif not args.no_snapshot:
        print("INCOMPLETE - no reset point taken. Start the job again to continue." if not complete else "Trial run - no reset point.")
    db.execute(text("select pg_advisory_unlock(:k)"), {"k": history.BUILD_LOCK})
    return 0 if (complete or args.limit is not None or args.no_snapshot) else 3


if __name__ == "__main__":
    sys.exit(main())
