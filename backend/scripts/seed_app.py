"""Seed the app's own settings: business rules, business date and demo users.

Run from the backend folder:
    python -m scripts.seed_app            # adds anything missing, keeps your changes
    python -m scripts.seed_app --reset    # puts every rule back to the factory default
"""
import sys

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import get_settings
from app.db import SessionLocal
from app.models.ar import AppUser, AuditLog, RuleConfig
from app.rules_defaults import DEFAULT_RULES

DEMO_USERS = [
    ("analyst@acme-demo.local", "Asha (AR Analyst)", "AR_ANALYST"),
    ("cashapp@acme-demo.local", "Carlos (Cash Application)", "CASH_APPLICATION"),
    ("collections@acme-demo.local", "Chen (Collections Analyst)", "COLLECTIONS_ANALYST"),
    ("supervisor@acme-demo.local", "Sofia (AR Supervisor)", "AR_SUPERVISOR"),
]


def main() -> int:
    reset = "--reset" in sys.argv
    rules = dict(DEFAULT_RULES)
    rules["business_date"] = ({"date": get_settings().business_date.isoformat()},
                              "Demo business date used by every rule instead of the real calendar.")
    with SessionLocal.begin() as db:
        for key, (value, desc) in rules.items():
            stmt = insert(RuleConfig).values(key=key, value=value, description=desc, updated_by="seed")
            if reset:
                stmt = stmt.on_conflict_do_update(index_elements=["key"],
                                                  set_={"value": value, "description": desc, "updated_by": "seed"})
            else:
                stmt = stmt.on_conflict_do_nothing(index_elements=["key"])
            db.execute(stmt)
        for email, name, role in DEMO_USERS:
            db.execute(insert(AppUser).values(email=email, display_name=name, role=role)
                       .on_conflict_do_nothing(index_elements=["email"]))
        db.add(AuditLog(actor="system", entity_type="rule", action="SEED_RULES_RESET" if reset else "SEED_RULES",
                        details={"keys": sorted(rules)}))
        n_rules = len(db.scalars(select(RuleConfig.key)).all())
        n_users = len(db.scalars(select(AppUser.id)).all())
    print(f"Rules in database: {n_rules}   Demo users: {n_users}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
