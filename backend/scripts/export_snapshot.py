"""Export the demo (snapshot) edition's data as static JSON (M15).

    $env:DATABASE_NAME = "ar_snapshot"; python -m scripts.export_snapshot

Writes snapshot/ in the project root:
  data/meta.json            when / what (counts, business date)
  data/work_items.json      every row of the Action Queue (what GET /api/work-items returns, plus what the browser needs for KPIs and the Excel export)
  data/details/<ENT>.json   one Record Detail per row (what GET /api/work-items/<ENT> returns)
  data/audit.json           the Audit Trail
  data/ptp.json             the PTP Tracker
  data/kpis_expected.json   what the real API answers for /api/kpis (several filters): the browser's own KPI code is tested against it
  data/files.json           the attachment manifest: which sample file (or exported file) belongs to which attachment id, and its pages
  data/texts/<id>.json      the read text of attachments that have no page images
  files/<id>/<name>         attachments that are not a plain sample file (files unpacked from a ZIP)
Everything is read through the real API code (a test client with a fixed user), so the files are exactly what the live system shows.

SAFETY: only e-mails whose source is sample / upload / history AND whose sample code is in the live or history set are exported (never mail
from a real sender); attachments of other e-mails are never copied; the demo mailbox address is replaced; nothing secret is read.
Refuses to run unless DATABASE_NAME is set (the clean snapshot database) or --any-database is given.
"""
import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from app.config import PROJECT_ROOT, get_settings

OUT = PROJECT_ROOT / "snapshot"
REPLACEMENTS: dict[str, str] = {}  # filled in main(): the demo mailbox address -> a harmless placeholder
PLACEHOLDER_MAILBOX = "demo-mailbox@example.invalid"
KPI_FILTERS = [{}, {"status": "CONFIRMED"}, {"company_code": "1000"}, {"classification": "PTP"}, {"decision": "AUTO_PROCESS"},
               {"from_date": "2026-09-01", "to_date": "2026-10-15"}, {"customer": "Rheinwerk"}, {"region": "EAST"}, {"q": "INV"},
               {"min_confidence": 80}, {"bsid_match": "false"}]


def clean(obj):
    """Replace the demo mailbox address anywhere in the data (audit details of clarifications mention it)."""
    raw = json.dumps(obj, ensure_ascii=False, default=str)
    for a, b in REPLACEMENTS.items():
        raw = raw.replace(a, b)
    return json.loads(raw)


def dump(path: Path, obj) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(clean(obj), ensure_ascii=False, separators=(",", ":"))
    path.write_text(data, encoding="utf-8")
    return len(data.encode("utf-8"))


def pages(client, url: str) -> list[dict]:
    out, page = [], 1
    while True:
        r = client.get(url + ("&" if "?" in url else "?") + f"page={page}&page_size=200")
        r.raise_for_status()
        body = r.json()
        out += body["items"]
        if len(out) >= body["total"] or not body["items"]:
            return out
        page += 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--any-database", action="store_true", help="allow the normal database (only for a trial; the safety rule still applies)")
    args = ap.parse_args(argv)
    s = get_settings()
    if not s.database_name and not args.any_database:
        print("Refusing: set DATABASE_NAME=ar_snapshot (the clean snapshot database) or pass --any-database.")
        return 1
    s.jwt_secret = s.jwt_secret or "snapshot-export-not-a-secret-0123456789"  # signs links that are replaced below
    REPLACEMENTS[s.outbound_redirect_to] = PLACEHOLDER_MAILBOX

    from fastapi.testclient import TestClient

    from app.api.auth import CurrentUser, current_user
    from app.businessdate import current_business_date
    from app.db import SessionLocal, get_db
    from app.gmail import sample_library
    from app.main import app
    from app.outbound import LANGUAGES

    db = SessionLocal()
    lib = sample_library.get_library()
    codes = set(sample_library.live_set(lib)) | set(sample_library.history_set(lib))
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[current_user] = lambda: CurrentUser("supervisor@acme-demo.local", "Sofia (AR Supervisor)", "AR_SUPERVISOR")
    client = TestClient(app)

    # ---- the whitelist: e-mails of the samples only
    allowed = {r.email_ref: r for r in db.execute(text(
        "select email_ref, source, sample_code, id, business_date from ar.email_message "
        "where source in ('sample', 'upload', 'history') and sample_code = any(:c)"), {"c": sorted(codes)})}
    total_emails = db.execute(text("select count(*) from ar.email_message")).scalar()
    print(f"E-mails in the database: {total_emails}; exported (live + history samples only): {len(allowed)}; left out: {total_emails - len(allowed)}")
    if OUT.exists():
        shutil.rmtree(OUT)
    sizes: dict[str, int] = {}

    # ---- rows
    rows = [r for r in pages(client, "/api/work-items?sort=received_at&order=desc") if r["email_ref"] in allowed]
    extra = {r.entry_id: dict(r._mapping) for r in db.execute(text(
        "select w.entry_id, w.payment_date, w.remittance_ref as payment_reference, b.belnr, b.gjahr, b.buzei, b.waers as bsid_currency, "
        "case when b.shkzg = 'H' then -b.wrbtr else b.wrbtr end as bsid_amount, k.spras, e.source, e.business_date as email_business_date "
        "from ar.work_item w join ar.email_message e on e.id = w.email_id left join sap.bsid b on b.id = w.bsid_id "
        "left join sap.kna1 k on k.kunnr = w.kunnr"))}
    for r in rows:
        x = extra[r["entry_id"]]
        r.pop("allowed_actions", None)  # worked out in the browser from the role
        r["export"] = {"payment_date": x["payment_date"], "payment_reference": x["payment_reference"], "belnr": x["belnr"], "gjahr": x["gjahr"],
                       "buzei": x["buzei"], "bsid_amount": x["bsid_amount"], "bsid_currency": x["bsid_currency"],
                       "language": LANGUAGES.get((x["spras"] or "").upper(), "en"), "source": x["source"],
                       "email_business_date": x["email_business_date"]}
    sizes["work_items.json"] = dump(OUT / "data" / "work_items.json", rows)

    # ---- details + attachment manifest
    manifest: dict[int, dict] = {}
    details_bytes, n_files = 0, 0
    samples_dir = Path(s.samples_root)
    for i, r in enumerate(rows, start=1):
        d = client.get(f"/api/work-items/{r['entry_id']}").json()
        d.pop("allowed_actions", None)
        d["resolved"] = r["resolved"]
        for sibling in d.get("same_email_items", []):
            sibling.pop("allowed_actions", None)
        code = allowed[r["email_ref"]].sample_code
        for a in d["attachments"]:
            a.pop("url", None)
            page_tpl = a.pop("page_url", None)
            entry = manifest.get(a["id"])
            if entry is None:
                src = samples_dir / code / a["filename"]
                if a["parent_id"] is None and src.exists():
                    entry = {"kind": "sample", "path": f"emails/{code}/{a['filename']}"}
                else:  # unpacked from a ZIP (or renamed): export the stored file itself
                    from app.storage import get_storage

                    uri = db.execute(text("select storage_uri from ar.email_attachment where id = :i"), {"i": a["id"]}).scalar()
                    dest = OUT / "files" / str(a["id"]) / a["filename"]
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(get_storage().get(uri))
                    entry = {"kind": "file", "path": f"{a['id']}/{a['filename']}"}
                    n_files += 1
                entry |= {"id": a["id"], "filename": a["filename"], "mime": a.get("mime_type"), "pages": a.get("page_count") if page_tpl else 0}
                manifest[a["id"]] = entry
            a["file"] = entry["path"] if entry["kind"] == "sample" else f"files/{entry['path']}"
            a["file_kind"] = entry["kind"]
            a["pages_url"] = f"pages/{a['id']}/{{page}}.jpg" if page_tpl else None
        details_bytes += dump(OUT / "data" / "details" / f"{r['entry_id']}.json", d)
        if i % 100 == 0:
            print(f"  details {i}/{len(rows)}")
    sizes["details/*.json"] = details_bytes

    # ---- text of attachments without page images (the viewer shows their text)
    texts = 0
    for aid, e in manifest.items():
        if not e["pages"] and (e["mime"] or "") != "application/pdf" and not (e["mime"] or "").startswith("image/"):
            lay = client.get(f"/api/attachments/{aid}/layout").json()
            dump(OUT / "data" / "texts" / f"{aid}.json", {"id": aid, "filename": lay["filename"], "text": lay["text"]})
            texts += 1
    dump(OUT / "data" / "files.json", list(manifest.values()))

    # ---- audit, promises, KPI oracle
    keep_entries = {r["entry_id"] for r in rows}
    audit = [a for a in pages(client, "/api/audit")
             if (a["entity_type"] == "work_item" and a["entity_id"] in keep_entries) or (a["entity_type"] == "email" and a["entity_id"] in allowed)
             or (a["entity_type"] == "ptp" and (a["entity_id"] or "").split("/")[0] in keep_entries)]
    sizes["audit.json"] = dump(OUT / "data" / "audit.json", audit)
    ptp = client.get("/api/ptp?page_size=200").json()
    all_ptp, page = ptp["items"], 1
    while len(all_ptp) < ptp["total"]:
        page += 1
        all_ptp += client.get(f"/api/ptp?page_size=200&page={page}").json()["items"]
    ptp["items"] = [p for p in all_ptp if p["entry_id"] in keep_entries]
    sizes["ptp.json"] = dump(OUT / "data" / "ptp.json", ptp)
    oracle = [{"filters": f, "kpis": client.get("/api/kpis", params=f).json()} for f in KPI_FILTERS]
    sizes["kpis_expected.json"] = dump(OUT / "data" / "kpis_expected.json", oracle)

    meta = {"generated_at": datetime.now(timezone.utc).isoformat(), "business_date": current_business_date(db).isoformat(),
            "work_items": len(rows), "emails": len(allowed), "attachments": len(manifest), "files_exported": n_files,
            "audit_rows": len(audit), "promises": len(ptp["items"]), "left_out_emails": total_emails - len(allowed),
            "by_source": {k: sum(1 for r in allowed.values() if r.source == k) for k in ("history", "sample", "upload")}}
    dump(OUT / "data" / "meta.json", meta)
    print(json.dumps(meta, indent=1))
    print({k: f"{v / 1024:.0f} KB" for k, v in sizes.items()}, f"| {texts} text files, {n_files} unpacked files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
