# M15 - Demo edition (snapshot) on GitHub Pages

Status: built and tested on the laptop (3 Nov 2026), not yet pushed / published. Safety check: PASSED (report `docs/reports/snapshot_check_2026-11-03.md`). Assembled site: 63 MB (limit 300).

## What it is
The permanent, free demo that needs no server: the same front-end, built with `VITE_DATA_SOURCE=snapshot`, published at the root of the GitHub Pages site (`/live/` stays the live edition while Azure runs). Everything works in the browser on static JSON; changes live in memory only ("Demo snapshot - changes reset on reload" banner + Reset button).

## What works / what does not
- Works: login by picking a user (no access code), Dashboard (KPIs and charts computed in the browser, so actions show at once), Action Queue (filters, sort, paging, bulk), Record Detail (e-mail, evidence highlights on the real PDF pages, BSID block, score breakdown, audit timeline, attachments), Confirm & Add to Excel (single and bulk), Reject, Escalate, Close as Duplicate, Request Clarification (shown as a preview, nothing is sent), Exported cases + Download .xlsx (ExcelJS in the browser), Audit Trail, promise status in the queue and the record (as exported), Knowledge Base. All rules are the server's rules: the action permissions (2,800 combinations) and the e-mail templates (6 languages) are tested against a fixture made by the Python code; the KPIs are tested against what the real API answered for the same rows (11 filter sets).
- Disabled (button greyed, "needs the live system"): Add / Update Invoice Details, Add BSID Invoice Details, Mark as Non-Duplicate - they match and score a record again, which needs the matching engine. Hidden: Demo Control, Gmail / Send sample / Process now, business-date controls, the promise re-check.

## How the data is made (all on the laptop, no Azure needed)
1. Create the empty database once (needs the postgres user): `CREATE DATABASE ar_snapshot OWNER ar_app;`
2. `$env:DATABASE_NAME = "ar_snapshot"; cd backend; python -m scripts.make_snapshot --fresh --export` (about 4 minutes):
   migrations, SAP reference data and demo users, the 187 history e-mails over the 3 months before 28 Oct (with the four users' actions), the 47 live-set e-mails processed and left OPEN (dated 26-28 Oct), promise check, then `scripts.export_snapshot` and `scripts.check_snapshot`. `DATABASE_NAME` swaps only the database name in `DATABASE_URL` (no secret is read). The scripts refuse to run on the normal database.
3. Output: `snapshot/data` (JSON, 12 MB, committed): work_items.json (504 rows), details/<ENT>.json, audit.json (2,846 rows), ptp.json, files.json (attachment manifest), texts/, kpis_expected.json (the oracle for the KPI test). `snapshot/files` = files unpacked from ZIP attachments (1 file).
4. The Pages workflow (`.github/workflows/frontend.yml`) builds both editions and runs `.github/scripts/build_site_files.py`: it copies ONLY the sample files named in the manifest from `data/samples`, renders the PDF page images (PyMuPDF, same resolution as the live viewer, JPEG) and fails if the site is over the limit. Page images and sample copies are not stored in git twice.

## Safety (export rules and the check)
- Only e-mails with source sample / upload / history AND a sample code of the live or history set are exported; attachments of any other e-mail are never copied. The clean database contains nothing else; real inbox mail never enters it.
- The demo mailbox address is replaced; the technical message id of each e-mail is not exported (it carries the build machine's timestamp and process id).
- `scripts.check_snapshot` fails unless: every e-mail address in the export is in the sample files, the SAP master data (ADR6), the read attachment texts or is a demo user (85 addresses, 0 unknown); no demo mailbox, Azure host name, JWT, private key, client-secret field, signed link or database URL appears; every work item and file belongs to a live / history sample. The first run found 234 "addresses" - all technical message ids - which is why that field is no longer exported. The gitleaks workflow ("Secret scan") must also be green on the commit that contains `snapshot/`.

## Timestamps
Pipeline audit entries (ingested, parsed, classified, matched) and row creation times of built e-mails are dated at the e-mail's own time (`history.stamp_pipeline`), so every record's Audit Timeline is in order (checked for all 504 records). `scripts.build_history --restamp` repairs history built before this existed (the history already built in Azure on 3 Nov still shows 3 Nov for those entries; fixing it also means taking the reset point again - to be decided).

## Tests (3 Nov 2026)
Back end 631 pass; front end 92 pass (new: the demo data source, rules parity, KPI comparison with the real API, the demo screens). Checked in a real browser against the assembled site: login without code, Dashboard, queue (504 records), record with PDF page images and 2 evidence highlights, confirm (Exported cases 354 to 355 with correct amounts), Reset (back to 354), promise status, Audit.
Not yet checked: the published site on GitHub Pages / in a private window on another computer, first-load time on the real site.
