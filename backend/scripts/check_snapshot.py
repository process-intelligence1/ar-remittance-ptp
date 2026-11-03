"""Safety check of the exported snapshot (M15) - must pass before anything is published.

    python -m scripts.check_snapshot           # reads snapshot/ (+ the clean database for the master data), writes docs/reports/snapshot_check_<date>.md

Fails (exit 1) when
  - an e-mail address in the export is not found in the sample files, the SAP master data (ADR6), the read attachment texts, or is not a demo user;
  - the demo mailbox, an Azure host name or a secret-looking string is in the export;
  - an exported file is not an attachment of a live / history sample, or a work item belongs to another e-mail source / sample code.
The report lists what was checked (counts) and the size of the data and of the site files that go with it.
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import text

from app.config import PROJECT_ROOT, get_settings

SNAP = PROJECT_ROOT / "snapshot"
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+")
FORBIDDEN = {
    "the demo mailbox": re.compile(r"processintelligence1", re.I),
    "an Azure host name": re.compile(r"azurecontainerapps\.io|database\.azure\.com|vault\.azure\.net|blob\.core\.windows\.net", re.I),
    "a bearer token / JWT": re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    "a private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "a client secret / token field": re.compile(r"client_secret|refresh_token|X-Admin-Key|access_token", re.I),
    "a signed download link": re.compile(r"[?&]token=[A-Za-z0-9_\-.]{20,}"),
    "a database URL": re.compile(r"postgres(?:ql)?(?:\+\w+)?://\S+:\S+@", re.I),
}
OK_SUFFIXES = ("@acme-demo.local", "@example.invalid", "@example.com", "@example.org")


def folder_size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0


def mb(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB"


def main() -> int:
    from app.db import SessionLocal
    from app.gmail import sample_library

    s = get_settings()
    if not (SNAP / "data" / "meta.json").exists():
        print("Nothing to check: run scripts.export_snapshot first.")
        return 1
    db = SessionLocal()
    lib = sample_library.get_library()
    codes = set(sample_library.live_set(lib)) | set(sample_library.history_set(lib))
    problems: list[str] = []

    # ---- 1. the whitelist of e-mail addresses: samples, SAP master data, read attachment texts, demo users
    known: set[str] = set()
    for code in codes:
        smp = lib.load(code)
        known |= {m.lower() for m in EMAIL.findall(" ".join(smp.headers.values()) + "\n" + smp.body)}
    known |= {(r[0] or "").lower() for r in db.execute(text("select smtp_addr from sap.adr6")) if r[0]}
    known |= {m.lower() for (t,) in db.execute(text("select text_content from ar.email_attachment where text_content is not null"))
              for m in EMAIL.findall(t)}
    known |= {(r[0] or "").lower() for r in db.execute(text("select email from ar.app_user"))}

    # ---- 2. every exported text file
    seen_addresses: dict[str, str] = {}
    files = [p for p in (SNAP / "data").rglob("*.json")]
    for p in files:
        raw = p.read_text(encoding="utf-8")
        for a in set(EMAIL.findall(raw)):
            seen_addresses.setdefault(a.lower(), p.relative_to(SNAP).as_posix())
        for what, rx in FORBIDDEN.items():
            if (m := rx.search(raw)):
                problems.append(f"{p.relative_to(SNAP).as_posix()}: contains {what} ({m.group(0)[:40]!r})")
    unknown = {a: f for a, f in seen_addresses.items() if a not in known and not a.endswith(OK_SUFFIXES)}
    for a, f in sorted(unknown.items()):
        problems.append(f"e-mail address not in the samples / SAP master data: {a} (first seen in {f})")

    # ---- 3. only live / history samples: the rows and the files
    meta = json.loads((SNAP / "data" / "meta.json").read_text(encoding="utf-8"))
    rows = json.loads((SNAP / "data" / "work_items.json").read_text(encoding="utf-8"))
    refs = {r["email_ref"] for r in rows}
    ok_emails = {r[0] for r in db.execute(text("select email_ref from ar.email_message where source in ('sample','upload','history') "
                                               "and sample_code = any(:c)"), {"c": sorted(codes)})}
    if refs - ok_emails:
        problems.append(f"{len(refs - ok_emails)} exported work item(s) belong to e-mails that are not live / history samples: {sorted(refs - ok_emails)[:5]}")
    manifest = json.loads((SNAP / "data" / "files.json").read_text(encoding="utf-8"))
    sample_root = Path(s.samples_root)
    for e in manifest:
        if e["kind"] == "sample":
            code = e["path"].split("/")[1]
            if code not in codes or not (sample_root / e["path"].split("/", 1)[1]).exists():
                problems.append(f"manifest file {e['path']} is not a live / history sample file")
    listed = {e["path"] for e in manifest if e["kind"] == "file"}
    on_disk = {p.relative_to(SNAP / "files").as_posix() for p in (SNAP / "files").rglob("*") if p.is_file()}
    if on_disk - listed:
        problems.append(f"files in snapshot/files that are not in the manifest: {sorted(on_disk - listed)[:5]}")

    # ---- 4. sizes
    sample_bytes = sum((sample_root / e["path"].split("/", 1)[1]).stat().st_size for e in manifest if e["kind"] == "sample")
    data_bytes, files_bytes = folder_size(SNAP / "data"), folder_size(SNAP / "files")
    pages = sum(e["pages"] or 0 for e in manifest)
    est_pages = pages * 70 * 1024
    total = data_bytes + files_bytes + sample_bytes + est_pages

    report = [f"# Snapshot safety check - {date.today().isoformat()}", "",
              f"Result: **{'PASSED' if not problems else 'FAILED'}** ({len(problems)} problem(s))", "",
              "## What was exported", f"- {meta['work_items']} work items from {meta['emails']} e-mails ({meta['by_source']}); {meta['left_out_emails']} other e-mail(s) in the database were NOT exported.",
              f"- {meta['attachments']} attachments in the manifest: {sum(1 for e in manifest if e['kind'] == 'sample')} are plain sample files (copied from data/samples when the site is built), "
              f"{sum(1 for e in manifest if e['kind'] == 'file')} unpacked from ZIP files are exported.",
              f"- {meta['audit_rows']} audit rows, {meta['promises']} promises, business date {meta['business_date']}.", "",
              "## Checks",
              f"- E-mail addresses found in the export: {len(seen_addresses)}; not in the sample files / SAP master data / read attachment texts / demo users: **{len(unknown)}** (must be 0).",
              "- Searched every exported JSON file for: " + ", ".join(FORBIDDEN) + ".",
              f"- Every work item belongs to a live / history sample e-mail (source sample / upload / history): {'yes' if not (refs - ok_emails) else 'NO'}.",
              f"- Every exported attachment file belongs to a live / history sample: {'yes' if not any('not a live' in p for p in problems) else 'NO'}.",
              "- The gitleaks workflow ('Secret scan') must also be green on the commit that contains snapshot/.", "",
              "## Size",
              f"- snapshot/data (JSON): {mb(data_bytes)}; snapshot/files: {mb(files_bytes)}",
              f"- sample files referenced by the manifest (copied at site build): {mb(sample_bytes)}",
              f"- PDF page images ({pages} pages, rendered at site build, estimate 70 KB each): {mb(est_pages)}",
              f"- **Estimated site size: {mb(total)}** (limit 300 MB). The measured size of the assembled site is added by scripts/build_site_files.py.", ""]
    if problems:
        report += ["## Problems", *[f"- {p}" for p in problems], ""]
    out = PROJECT_ROOT / "docs" / "reports" / f"snapshot_check_{date.today().isoformat()}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    print(f"Report: {out}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
