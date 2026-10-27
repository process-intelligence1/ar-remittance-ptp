"""Re-fetch e-mails that were skipped as "ignored system sender" but are no longer on the ignore list.

Run from the backend folder:
    python -m scripts.refetch_ignored          # LIST the AR-Ignored messages and what the current rule says
    python -m scripts.refetch_ignored --yes    # remove AR-Ignored from those no longer ignored;
                                               # the next poll (Azure) stores and processes them
Uses the rule in THIS database (laptop); make sure Azure has the same rule before its next poll.
"""
import sys

from app.db import SessionLocal
from app.gmail.client import build_service
from app.gmail.refetch import list_ignored, release


def main(argv: list[str]) -> int:
    service = build_service()
    with SessionLocal() as db:
        msgs = list_ignored(db, service)
    back = [m for m in msgs if m.still_ignored_by is None]
    print(f"{len(msgs)} Gmail message(s) labelled AR-Ignored:")
    for m in msgs:
        verdict = f"still ignored ({m.still_ignored_by})" if m.still_ignored_by else "NO LONGER IGNORED -> re-fetch"
        orig = f" (forwarded from {m.original_sender})" if m.original_sender else ""
        print(f"  {m.gmail_id}  {m.sender}{orig}  '{(m.subject or '')[:60]}'  -> {verdict}")
    if "--yes" not in argv:
        print(f"\n{len(back)} to re-fetch. Nothing changed (list only). Run again with --yes.")
        return 0
    n = release(service, [m.gmail_id for m in back])
    print(f"\nRemoved AR-Ignored from {n} message(s); the next poll will store them.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
