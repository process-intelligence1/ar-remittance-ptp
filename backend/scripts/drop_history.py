"""LAPTOP ONLY: remove the history e-mails (source 'history') and everything that belongs to them, so scripts.build_history can be tried again.

    python -m scripts.drop_history          # asks nothing: it refuses to run when ENVIRONMENT=demo (Azure)

Deletes: the history e-mails with their attachments rows, extractions, work items, candidates, promises and outbound e-mails (cascade),
the audit entries of those work items / e-mails, and the reset point (schema demo_reset, rebuilt at the end of a full build).
It does NOT delete files from the storage folder (they are overwritten by the next build).
"""
import sys

from sqlalchemy import text

from app.config import get_settings
from app.db import SessionLocal


def main() -> int:
    if get_settings().environment == "demo":
        print("Refusing: ENVIRONMENT=demo (Azure). This script is for the laptop database only.")
        return 1
    db = SessionLocal()
    refs = [r[0] for r in db.execute(text("select email_ref from ar.email_message where source = 'history'"))]
    entries = [r[0] for r in db.execute(text("select w.entry_id from ar.work_item w join ar.email_message e on e.id = w.email_id where e.source = 'history'"))]
    db.execute(text("delete from ar.audit_log where (entity_type = 'work_item' and entity_id = any(:e)) or (entity_type = 'email' and entity_id = any(:r)) "
                    "or (entity_type = 'ptp' and split_part(entity_id, '/', 1) = any(:e))"), {"e": entries, "r": refs})
    db.execute(text("update ar.email_message set parent_email_id = null where parent_email_id in (select id from ar.email_message where source = 'history')"))
    db.execute(text("update ar.work_item set duplicate_of_id = null where duplicate_of_id in (select w.id from ar.work_item w join ar.email_message e on e.id = w.email_id where e.source = 'history')"))
    db.execute(text("delete from ar.email_message where source = 'history'"))
    db.execute(text("drop schema if exists demo_reset cascade"))
    db.commit()
    print(f"Removed {len(refs)} history e-mails, {len(entries)} work items and the reset point.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
