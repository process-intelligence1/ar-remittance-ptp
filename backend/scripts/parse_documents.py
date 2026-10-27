"""Read e-mail bodies and attachments (text, tables, word positions, OCR).

Run from the backend folder:
    python -m scripts.parse_documents                    # stored e-mails not parsed yet
    python -m scripts.parse_documents --email EML-000037 # one e-mail
    python -m scripts.parse_documents --reparse          # parse everything again
    python -m scripts.parse_documents --samples-report   # all sample folders, no database
                                                         # -> docs/reports/M02_samples_report.md
"""
import hashlib
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import select

from app.config import PROJECT_ROOT
from app.documents.body import parse_body
from app.documents.common import DocumentTimeout
from app.documents.router import kind_of, timed_parse
from app.gmail.parsing import clean_body
from app.gmail.sample_sender import load_sample, samples_root

REPORT = PROJECT_ROOT / "docs" / "reports" / "M02_samples_report.md"


def parse_stored(argv: list[str]) -> int:
    from app.db import SessionLocal
    from app.documents.service import parse_email
    from app.models.ar import EmailMessage

    reparse = "--reparse" in argv
    with SessionLocal() as db:
        q = select(EmailMessage).order_by(EmailMessage.id)
        if "--email" in argv:
            q = q.where(EmailMessage.email_ref == argv[argv.index("--email") + 1])
        elif not reparse:
            q = q.where(EmailMessage.status.in_(("NEW", "FAILED")))
        emails = db.scalars(q).all()
        total = Counter()
        for e in emails:
            s = parse_email(db, e, reparse=reparse)
            total.update(parsed=s.parsed, reused=s.reused, skipped=s.skipped, failed=s.failed, ms=s.ms, saved=s.saved_ms)
            print(f"{s.email_ref}: parsed {s.parsed}, reused {s.reused}, skipped {s.skipped}, failed {s.failed}, "
                  f"body tables {s.body_tables}, {s.ms / 1000:.1f} s" + (f"  ERRORS: {s.errors}" if s.errors else ""))
        print(f"\n{len(emails)} e-mail(s): parsed {total['parsed']}, reused {total['reused']} "
              f"(saved {total['saved'] / 1000:.1f} s), skipped {total['skipped']}, failed {total['failed']}, "
              f"{total['ms'] / 1000:.1f} s reading")
    return 1 if total["failed"] else 0


def samples_report() -> int:
    """Every sample folder: body + attachments. Reuse by SHA-256 within the run (like the database)."""
    rows, cache = [], {}
    saved_ms = 0
    started = time.perf_counter()
    codes = sorted(p.name for p in samples_root().iterdir() if (p / "body.txt").exists())
    for code in codes:
        sample = load_sample(code)
        body = clean_body(sample.body)
        layout, lang = parse_body(body)
        files = [p for p in sample.attachments]
        rows.append({"code": code, "file": "(body)", "type": "body", "method": "body", "status": "PARSED",
                     "pages": None, "chars": len(body), "conf": None, "lang": lang, "ms": 0, "reused": False,
                     "body_only": not files, "tables": len(layout["tables"]), "note": ""})
        for p in files:
            data = p.read_bytes()
            sha = hashlib.sha256(data).hexdigest()
            row = {"code": code, "file": p.name, "type": kind_of(p.name, None, data), "body_only": False}
            if sha in cache:  # identical file already read in this run
                row.update(cache[sha], reused=True)
                saved_ms += cache[sha]["ms"]
            else:
                try:
                    r, ms = timed_parse(p.name, None, data)
                    row.update(method=r.method, status=r.status, pages=r.page_count, chars=len(r.text),
                               conf=r.ocr_confidence, lang=r.language, ms=ms, tables=len(r.tables), note=r.note or "")
                except DocumentTimeout as exc:
                    row.update(method="-", status="FAILED", pages=None, chars=0, conf=None, lang=None, ms=0,
                               tables=0, note=f"timeout ({exc})")
                except Exception as exc:
                    row.update(method="-", status="FAILED", pages=None, chars=0, conf=None, lang=None, ms=0,
                               tables=0, note=f"{type(exc).__name__}: {exc}"[:200])
                cache[sha] = {k: row[k] for k in ("method", "status", "pages", "chars", "conf", "lang", "ms", "tables", "note")}
                row["reused"] = False
            rows.append(row)
            print(f"{code} {p.name}: {row['method']} {row['status']} {row['chars']} chars "
                  f"conf={row['conf']} {row['ms']} ms{' (reused)' if row['reused'] else ''}", flush=True)
    write_report(rows, codes, saved_ms, time.perf_counter() - started)
    failed = [r for r in rows if r["status"] == "FAILED"]
    print(f"\nReport: {REPORT}\n{len(rows)} items, {len(failed)} failed")
    return 1 if failed else 0


def write_report(rows: list[dict], codes: list[str], saved_ms: int, wall_s: float) -> None:
    att = [r for r in rows if r["type"] != "body"]
    by_type = defaultdict(list)
    for r in att:
        by_type[r["type"]].append(r)
    lines = ["# M02 — sample parsing report", "",
             f"{len(codes)} sample e-mails, {len(att)} attachments, run time {wall_s:.0f} s "
             f"(time saved by reusing identical files: {saved_ms / 1000:.1f} s, "
             f"{sum(1 for r in att if r['reused'])} files reused).", "",
             "## Summary by file type", "",
             "| Type | Files | Parsed | Skipped | Failed | Methods | Avg chars | Avg OCR conf | Avg ms (excl. reused) |",
             "|---|---|---|---|---|---|---|---|---|"]
    for t, rs in sorted(by_type.items()):
        fresh = [r for r in rs if not r["reused"]]
        confs = [r["conf"] for r in rs if r["conf"] is not None]
        methods = ", ".join(f"{m} {n}" for m, n in Counter(r["method"] for r in rs).most_common())
        lines.append(f"| {t} | {len(rs)} | {sum(r['status'] == 'PARSED' for r in rs)} | "
                     f"{sum(r['status'] == 'SKIPPED' for r in rs)} | {sum(r['status'] == 'FAILED' for r in rs)} | "
                     f"{methods} | {sum(r['chars'] for r in rs) // max(1, len(rs))} | "
                     f"{(sum(confs) / len(confs)) if confs else 0:.1f} | "
                     f"{sum(r['ms'] for r in fresh) // max(1, len(fresh))} |")
    bodies = [r for r in rows if r["type"] == "body"]
    body_only = [r for r in bodies if r["body_only"]]
    lines += ["", "## E-mail bodies", "",
              f"{len(bodies)} bodies; **{len(body_only)} body-only e-mails** (no attachment); "
              f"{sum(1 for r in bodies if r['tables'])} bodies contain a table "
              f"({sum(1 for r in body_only if r['tables'])} of the body-only ones).", "",
              "## Every item", "",
              "| Sample | File | Type | Body-only | Method | Status | Pages | Chars | OCR conf | Lang | Tables | ms | Reused | Note |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['code']} | {r['file']} | {r['type']} | {'yes' if r['body_only'] else ''} | {r['method']} | "
                     f"{r['status']} | {r['pages'] or ''} | {r['chars']} | {'' if r['conf'] is None else r['conf']} | "
                     f"{r['lang'] or ''} | {r['tables']} | {r['ms']} | {'yes' if r['reused'] else ''} | "
                     f"{(r['note'] or '').replace('|', '/')} |")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(samples_report() if "--samples-report" in sys.argv else parse_stored(sys.argv[1:]))
