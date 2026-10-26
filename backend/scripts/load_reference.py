"""Load the SAP reference data from the Excel files in data/seed into PostgreSQL.

Run from the backend folder:
    python -m scripts.load_reference

It is safe to run again at any time: each table is emptied first, then re-loaded,
all inside one transaction (if anything fails, nothing is changed).
"""
import datetime as dt
import sys
import time
from pathlib import Path

from openpyxl import load_workbook
from sqlalchemy import delete, insert

from app.config import PROJECT_ROOT
from app.db import SessionLocal
from app.models import sap

SEED = PROJECT_ROOT / "data" / "seed"

# (Excel file, sheet, table class)
SHEETS = [
    ("Org_Currency_Config.xlsx", "T001", sap.T001),
    ("Org_Currency_Config.xlsx", "TCURX", sap.Tcurx),
    ("Org_Currency_Config.xlsx", "T052", sap.T052),
    ("Org_Currency_Config.xlsx", "TCURR", sap.Tcurr),
    ("Customer_Master_Data.xlsx", "KNA1", sap.Kna1),
    ("Customer_Master_Data.xlsx", "KNB1", sap.Knb1),
    ("Customer_Master_Data.xlsx", "KNBK", sap.Knbk),
    ("Customer_Master_Data.xlsx", "KNVP", sap.Knvp),
    ("Customer_Master_Data.xlsx", "ADR6", sap.Adr6),
    ("BSID_Open_Items.xlsx", "BSID", sap.Bsid),
    ("BSAD_Cleared_Items.xlsx", "BSAD", sap.Bsad),
]
CATALOG_FILES = {
    "BSID_Open_Items.xlsx": "BSID",
    "BSAD_Cleared_Items.xlsx": "BSAD",
    "Customer_Master_Data.xlsx": "CUSTOMER",
    "Org_Currency_Config.xlsx": "ORG_CURRENCY",
}
BATCH = 2000


def read_sheet(path: Path, sheet: str) -> list[dict]:
    wb = load_workbook(path, read_only=True, data_only=True)
    rows = wb[sheet].iter_rows(values_only=True)
    header = [str(h).strip().lower() for h in next(rows)]
    out = []
    for r in rows:
        if r is None or all(v is None for v in r):
            continue
        rec = {}
        for k, v in zip(header, r):
            if isinstance(v, dt.datetime):
                v = v.date()
            elif isinstance(v, str):
                v = v.strip() or None
            rec[k] = v
        out.append(rec)
    wb.close()
    return out


def coerce(model, rec: dict) -> dict:
    """Keep only known columns; turn numbers into text where the column is text (keeps leading zeros)."""
    cols = {c.key: c for c in model.__table__.columns if c.key != "id"}
    clean = {}
    for k, v in rec.items():
        if k not in cols:
            continue
        if v is not None and cols[k].type.python_type is str and not isinstance(v, str):
            v = str(v)
        clean[k] = v
    return clean


def main() -> int:
    if not SEED.exists():
        print(f"Seed folder not found: {SEED}")
        return 1
    start = time.time()
    with SessionLocal.begin() as db:
        # 1. Empty tables (children first is not needed - reference tables have no foreign keys)
        for _, _, model in SHEETS:
            db.execute(delete(model))
        db.execute(delete(sap.FieldCatalog))

        # 2. Load each sheet
        for file, sheet, model in SHEETS:
            records = [coerce(model, r) for r in read_sheet(SEED / file, sheet)]
            for i in range(0, len(records), BATCH):
                if records[i:i + BATCH]:
                    db.execute(insert(model), records[i:i + BATCH])
            print(f"  {model.__tablename__:<6} {len(records):>6} rows   <- {file} / {sheet}")

        # 3. Field descriptions (tooltips / Knowledge Base)
        n = 0
        seen = set()
        for file, source in CATALOG_FILES.items():
            for r in read_sheet(SEED / file, "Field_Descriptions"):
                field = r.get("field")
                if not field or (source, field) in seen:
                    continue
                seen.add((source, field))
                db.execute(insert(sap.FieldCatalog).values(
                    source_table=source, field=str(field), description=r.get("description"),
                    relevance=r.get("relevance"), notes=r.get("notes")))
                n += 1
        print(f"  field_catalog {n:>3} rows")
    print(f"Reference data loaded in {time.time() - start:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
