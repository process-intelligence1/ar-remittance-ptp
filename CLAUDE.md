# Project briefing for Claude Code

## What this project is
A demo, enterprise-style AR Remittance & Promise-to-Pay (PTP) application.
Customer e-mails arrive in processintelligence1@gmail.com, are read (text + OCR),
classified, matched to open SAP items (BSID), scored with the Knowledge Base
formula, and handled by AR users in a web workbench with a full audit trail.

The owner is not an experienced engineer: explain what each command does in
one plain sentence before running it, and summarise results in plain language.

## Environment (owner's laptop)
- Windows, PowerShell (inside VS Code), 8 GB RAM - keep things light, no Docker locally.
- Project folder: D:\Finance\AR_Remittance  (GitHub: process-intelligence1/ar-remittance-ptp, PUBLIC)
- Secrets folder: D:\Finance\Secret  (OUTSIDE the project)
- PostgreSQL 17 on localhost:5432, database ar_demo, app user ar_app
- Python 3.12 (virtual env at backend\.venv), Node.js LTS, Tesseract OCR at C:\Program Files\Tesseract-OCR

## Stack (decided)
- Backend: Python + FastAPI, SQLAlchemy 2, Alembic, PostgreSQL. One backend only (no Node API).
- Worker: Python, scheduled; jobs queued in the ar.job table (no Redis/Celery).
- Documents: PyMuPDF + pdfplumber, python-docx, openpyxl/pandas, OpenCV + Tesseract.
- Extraction: rules + small classifier. No local LLM (RAM). Optional free hosted LLM switch later.
- Front-end: React + Vite + TypeScript, reusing the prototype's own CSS look; TanStack Query/Table; Chart.js.
- Cloud (demo env): Azure Container Apps (API + scheduled worker job), Azure Database for PostgreSQL
  (B1ms), Blob Storage, Key Vault, Static Web Apps, App Insights. Deployed by GitHub
  Actions + Bicep. GitHub Container Registry (not Azure Container Registry).

## Hard rules
1. ZERO COST. Never create or suggest paid resources. Azure: consumption plans only, min replicas 0,
   no VMs, no public IPs, no ACR, B1ms Postgres only, LRS storage, Document Intelligence F0 only.
2. NEVER read, print, copy or commit secrets: .env, anything in D:\Finance\Secret, client_secret*.json,
   token files, passwords. If a value is needed in .env, ask the owner to type it in themselves.
3. Every outgoing e-mail goes ONLY to processintelligence1@gmail.com (OUTBOUND_MODE=redirect),
   stating the intended recipient in the subject/body.
4. SAP is simulated in PostgreSQL: schema "sap" (BSID, BSAD, KNA1, ...). Confirm & Update SAP moves
   an item from sap.bsid to sap.bsad; partial payments reduce the open amount, the rest stays open.
   No discounts.
5. Database changes only through Alembic migrations. Never edit tables by hand.
6. Ask before: git push, deleting files, changing anything outside D:\Finance\AR_Remittance,
   anything in Azure.
7. The GitHub repo and the container image are PUBLIC. Never commit secrets (rule 2), the Azure app
   URL or other environment URLs (write "see GitHub environment \"demo\" / Azure portal"), or real
   customer data - samples and SAP data are synthetic. Secret scanning push protection is on; run the
   "Secret scan" workflow (gitleaks, values redacted) before anything sensitive-looking is merged.

## Business decisions
- One row per INVOICE (ar.work_item); several rows can belong to one e-mail.
- E-mail type when read: REMITTANCE / PTP / OUT_OF_SCOPE (an e-mail can contain both remittance
  and PTP lines). Final classification per row: REMITTANCE / PTP / DUPLICATE / EXCEPTION / OUT_OF_SCOPE.
- Invoice-number matching (replaces the prototype's "digit match length"): extracted invoice number
  vs BSID XBLNR (primary); exact BELNR / VBELN matches accepted as alternates. Both sides normalised
  (upper case; spaces and - / . removed; leading zeros removed). Levels: EXACT 1.00 (fast path
  eligible); NEAR 0.70 = exactly one character differs and it is an OCR confusion (0/O, 1/I/L, 5/S,
  8/B, 2/Z) -> always review, "Possible OCR misread"; NONE 0.00 -> EXCEPTION "No BSID match found".
  Stored on ar.work_item as match_field (XBLNR/BELNR/VBELN), match_level, invoice_match_score.
- Scoring per Knowledge Base: weights 0.35 invoice match, 0.30 amount, 0.10 sender->company code,
  0.05 name, 0.10 date; raw / 0.90 = formula confidence %. Fast path: EXACT + BSID open + same currency +
  amount within 2% -> 92%; EXACT + amount missing -> 91%. Confidence = max(fast-path value, formula) - the
  formula is always calculated; work_item.confidence_source says which won (FAST_PATH | FORMULA); the fast
  path decides category / decision. 92 / 91 live in ar.rule_config "fast_path".
  >=80 + BSID = Auto Process; >=80 no BSID = Exception; 40-79 Manual Review; <40 Manual Investigation.
  KB worked example recalculated (invoice 23756669 vs BSID 23756668, $13,497.36 vs $13,464.77, name 0.957,
  144 days, sender mapped): as written 9/8 is no OCR pair -> NONE, 56.4% EXCEPTION; OCR variant (8 read as
  B) -> NEAR, 83.7% Manual Review; exact number -> formula 95.3% > fast path 92% -> 95.3% (FORMULA), Auto Process.
  Rules live in ar.rule_config (defaults in backend/app/rules_defaults.py).
- Payments without invoice numbers: find open invoices summing to the amount; always send to review.
- Demo "business date" (default 2026-10-28) is used by all rules instead of the real date.
- Payer/currency cluster: same customer's past items in the same currency from the same sender
  domain; leave blank when there is not enough history.
- Roles: AR_ANALYST, CASH_APPLICATION, COLLECTIONS_ANALYST, AR_SUPERVISOR.
- Demo Control page: Reset demo (restores the reset point, schema demo_reset, with ~200 history e-mails incl. actions per
  invoice), Send sample e-mail (Gmail import with the customer as sender), Upload sample, Process now,
  business date. ~35 samples held back for live sending.

## Order, quality, hosting and working style
- Quality first, no target dates: a module is done only when ALL its "Done when" checks pass. Order: M07, M08, M09, M10,
  M11, M15, M13, M14 (M12 dropped). Azure runs the live demo while the free account lasts (never upgrade, never click
  Upgrade); the permanent shareable demo is snapshot mode on GitHub Pages (M15), exported while Azure still runs. The
  worker is host-neutral (`python -m app.worker --once`).
- Working style (saves usage): explanations one short line; summaries under 10 lines; show test results as counts
  (details only for failures); do not re-read large files - search them.
- Scope: M08 front-end gets ALL data through one layer `frontend/src/data/` with two implementations, "live" (API) and
  "snapshot" (static JSON), chosen by VITE_DATA_SOURCE; screens never call fetch directly, actions also go through the layer;
  demo login + demo access code (Key Vault) is the final login. M10 lean (commitments, kept / partially kept / broken, alert
  + escalation, PTP tracker; no reliability scoring). M11: Reset demo (reset point in schema demo_reset), send sample,
  business date, 3-month history with actions per invoice, history e-mails get source 'history' (upload sample only if time
  allows). M12 DROPPED. M13 lite (secret scan, dependency alerts, docs/SECURITY.md; no budget automation / Defender). M14:
  presenter runbook (live link + permanent GitHub Pages link) + accuracy summary from existing reports, no dashboard page.
- M15 snapshot mode: export script `scripts.export_snapshot` (all screen data, e-mail texts, attachment files, evidence,
  candidates, KPI inputs, audit, PTP, Knowledge Base). SAFETY: export ONLY e-mails whose source is sample, upload or history
  (never e-mails from real senders in the inbox) plus their work items, attachments and audit entries; run gitleaks and a
  check for e-mail addresses not in the sample / customer master data before publishing. Front-end built with
  VITE_DATA_SOURCE=snapshot, deployed to GitHub Pages by GitHub Actions; actions work in the browser with a "Demo snapshot -
  changes reset on reload" banner and Reset button; outbound e-mails shown as previews; Gmail / Process now hidden; KPIs and
  chart data computed in the browser so actions update the Dashboard immediately. Done when: link works in incognito on
  another computer, all screens work, actions update the Dashboard, Reset works, no secrets / real e-mails (check report),
  site < 300 MB, first load < 5 s.

## Data
- data/seed/*.xlsx  - SAP reference data (BSID 4,840 open items, 71 customers, 6 company codes).
- data/samples/emails/<CODE>/ - 234 sample e-mails (body.txt + attachments). Folder prefix = scenario:
  R = remittance, P = PTP, P06 = payment + promise in one e-mail, P03R/P05R = the payment that follows
  an earlier PTP (P03/P05; no new promise in the text), O = out of scope (O01-O07 = the 7 categories).

## Plan status
- Day 1 done: tools installed, repo created, local database created.
- Day 2: backend skeleton, tables (Alembic), reference data loaded, first API - see docs/DAY2_GUIDE.md.
- Day 3 done (Milestone 1): API live in Azure Container Apps - see docs/DAY3_GUIDE.md.
  API URL: see GitHub environment "demo" / Azure portal (never write it in the repo). rg-ar-demo (centralindia):
  ar-api, cae-ar-demo, psql-ar-demo-snjjnahqgx3b4 (B1ms, data loaded), kv-ardemo-snjjnahqgx3b4,
  id-ar-api, log-ar-demo, policy "allowed resource types"; budget-ar-demo ($1) on the subscription.
  Azure account processintelligence1@outlook.com (Free Trial, spending limit on).
  Code deploys: push to main -> .github/workflows/deploy.yml (OIDC, environment "demo"; the build runs,
  then the deploy WAITS for the owner's approval - required reviewer). Infra deploys: .\infra\deploy.ps1 [-WhatIf] (rotates DB password each run).
  Image ghcr.io/process-intelligence1/ar-api is PUBLIC (240 MB compressed): no GHCR pull token (removed from
  Bicep + Key Vault 27 Oct 2026). Run deploy.ps1 with -NoClientIp (the laptop uses its local database).
- M01 done (Gmail ingestion + sample sender) - see docs/modules/M01_gmail_ingestion.md.
  Storage account stardemosnjjnahqgx3b4 / container ar-files; Gmail token in Key Vault "gmail-token"
  (Google app in TESTING mode: token expires ~3 Nov 2026 -> re-run scripts.gmail_auth + upload).
  Container runs `alembic upgrade head` on start. Tests: `python -m pytest` in backend (525 pass).
  Whole inbox is processed (NO date cut-off) except rule "ignored_senders" = ONLY the domains
  github.com, google.com, accounts.google.com, microsoft.com, azure.com, anthropic.com, claude.ai,
  claude.com (+ subdomains); NO address patterns (noreply@ ERP senders send real remittances, e.g.
  R19-0112). Ignored: not stored; audit EMAIL_IGNORED + Gmail label AR-Ignored. scripts.purge_ignored
  removes old ones; scripts.refetch_ignored releases AR-Ignored mail the current rule no longer ignores.
  Only Azure polls (POLLER_ENABLED=true there; laptop needs --force). /api/admin/* needs header
  X-Admin-Key (Key Vault "admin-api-key"; empty = admin off). Sample sends dated now, X-Original-Date kept.
- M02 done (document reading + OCR) - see docs/modules/M02_document_reading.md and
  docs/reports/M02_samples_report.md (234/234 samples parse). app/documents/: PDF text layer or OCR
  per page (mixed), images, DOCX, XLSX (data_only, ISO dates), CSV, HTML; body tables (HTML or
  aligned text). Reuse by SHA-256 (parse_reused). 120 s per-document deadline. Docker image has
  Tesseract + 7 languages; workflow keeps the 3 newest GHCR versions + the running one.
  OCR in Azure: only 1-2 test files on the API container until the M06 worker.
- M03 done (classification) - see docs/modules/M03_classification.md and
  docs/reports/M03_classification_report.md. app/classification/: keyword rules (EN/DE/FR/ES/PT/JA,
  lexicons.py) + small TF-IDF/logistic-regression model asked below 70 % confidence. Settings in
  ar.rule_config "classification". Samples 234/234 (rules, and rules + model cross-validated); new
  hand-written wording first try 15/18 (data/eval/classification_unseen.json - both batches since used
  for fixes). scikit-learn is LAPTOP-ONLY (requirements-dev.txt, training); the image predicts with numpy
  from app/classification/model.npz (keeps the image ~50 MB smaller). Retrain: scripts.train_classifier.
  scripts.classify; POST /api/admin/emails/{ref}/classify; Gmail labels AR-Remittance/AR-PTP/AR-OutOfScope
  only where Gmail is polled (Azure). Tests must never reach real Gmail (conftest turns POLLER_ENABLED on).
- Public repo + image (27 Oct 2026): gitleaks scan of full history, files and stored images was clean
  (workflow "Secret scan"); the app URL stays in 3 old commits (accepted - not a secret). Image slimmed
  251 -> 236 MB: base image pinned by digest, large libraries (requirements-heavy.txt: PyMuPDF, OpenCV,
  numpy, Pillow) in their own layer /opt/heavy, no pip, uvicorn without unused extras; OpenCV stays (a
  Pillow-only swap lowered OCR confidence - rejected). Workflow "Image size report" = layer breakdown
  without pushing. Clean-up keeps the 3 newest versions + whatever Azure runs. Deploys wait for the
  owner's approval (environment "demo" reviewer). Known, not fixed: OpenCV minAreaRect returns -90..0 here,
  so M02 deskew skips some tilted scans (e.g. R19-0114 at 0.24 deg, R29-0161).
- M04 done (extraction, deployed fb3168b) - see docs/modules/M04_extraction.md, docs/reports/M04_extraction_report.md.
  app/extraction/: ar.extraction (header) + ar.extraction_line (per invoice / instalment, evidence JSON);
  normalise_ref() in refs.py is THE invoice-number normalisation (used by M05). Own date parser (EN/DE/FR/
  ES/PT/JA, Japanese eras, relative promise dates vs the e-mail date). Invoice currency only when stated;
  payment currency + FX rate kept apart, nothing converted. scripts.extract [--reclean];
  POST /api/admin/emails/{ref}/extract. Evaluated with a HELD-OUT third (every 3rd sample per scenario, never
  studied): referenced remittance lines - number in BSID 95.5 % (dev 95.7), strict hit 80.2 % (dev 79.7;
  target 85 % MISSED), hit incl. deliberate part-payments 91.9 %, lines = stated total 95.9 % of held-out
  remittances (dev 88.3); without the 5 no-match scenarios (R02 R04 R06 R16 R26) strict hit 84.8 % held-out.
  60/60 PTP lines have a promise date. Also fixed: M01 reply cleaner cut instalment lists; M03 fold() collapsed
  aligned "Label   value" spacing (fold(keep_spaces=True)).
- M05 done (matching, deployed bacaad3) - see docs/modules/M05_matching.md, docs/reports/M05_matching_report.md.
  app/matching/: customers (INVOICE > SENDER_ADDRESS > CUSTOMER_NUMBER > IBAN > SENDER_DOMAIN > NAME; KNVP RG
  payers), invoice_match (EXACT/NEAR/NONE), scoring (confidence = max(fast path, formula), stored with
  confidence_source + formula_confidence), unreferenced (0.5 %, <= 6 invoices, always review), duplicates
  (values within 7 days or same attachment; same row kind only). ar.work_item one per invoice (+ match_candidate,
  ptp_commitment); ENT- ids from ar.entry_id_seq. scripts.match [--rematch]; POST /api/admin/emails/{ref}/match.
  Samples (504 rows): dev 65 % Auto / 22 % Review / 4 % Exception / 5 % Duplicate; HELD-OUT 61 % / 23 % / 4 % /
  10 %. Customer identified 215/217; agrees with ADR6 sender 97.6 %, quoted customer no. 98.8 %, owner of exactly
  matched invoices 99.5 %. P03-0193 JP-26-002271 -> 102419 SGD 8,300 (92 % FAST_PATH, Auto). Re-sent sample ->
  DUPLICATE. Fast path applied to 361 rows: formula higher for 283, fast-path value used for 78.
- M06 done (pipeline + worker, deployed 85ed8b0 + schedule change) - see docs/modules/M06_pipeline.md.
  app/pipeline.py (read -> classify -> extract -> match; resumes at the failed stage; audit per stage), app/jobs.py
  (ar.job queue, retries after 1 min / 5 min, max 3, SKIP LOCKED), app/worker.py (`python -m app.worker --once|--loop`;
  HOST-NEUTRAL: no Azure code, any scheduler can run it). Last attempt with an unreadable attachment -> continues with
  body + readable files, rows go to review with reason "Attachment unreadable" (never auto-processed). Azure: Container
  Apps Job ar-worker, cron */10 (parameter workerCron), 0.5 vCPU / 1 GiB. POST /api/admin/process-now (X-Admin-Key)
  starts the job at once via the Azure management API with the API's identity - custom role "AR Worker Job Starter" =
  only Microsoft.App/jobs/start/action, assigned on the job resource only (app/azure_jobs.py is the only Azure-specific
  code). GET /api/admin/jobs, scripts.process (laptop). Measured in Azure: idle run 37-39 s, 1 e-mail 66 s, 12-e-mail
  backlog incl. OCR 134 s; 5-minute schedule would use 91 % of the free grant, 10 minutes uses ~46 %. Real test: R19-0116
  sent from the laptop -> 2 AUTO_PROCESS work items; the 12 older Azure e-mails (R21-R32) all processed. Tests: 543 pass.
  The Azure policy now also allows Microsoft.App/jobs + Microsoft.Authorization/roleDefinitions.
- Next: M07, M08 (data-source layer from the start), M09, M10 lean, M11, M15, M13 lite, M14 (see docs/BUILD_PLAN.md).

## Open issues (as of 28 Oct 2026)
Known weak spots and deferred work - check here before planning a module.
- Accuracy / known weak scenarios
  - M04 strict hit 80 % < 85 % target: mostly deliberate part-payments (R03, R07, R27, P08 instalments) and
    exception scenarios where no line can match BSID (R02 amount column empty, R04 / R16 unknown numbers, R06
    other currency, R26). Real reading errors left: OCR misreads in scans (R21-0123, R26-0149 totals; R03-0034
    5947.10 for 947.10; R19-0115 / R26-0149 numbers) - M05 sends them to review.
  - Not in any sample, proven by unit tests only: FX rates, REM- references, relative promise dates, credit-note
    formats, IBAN payers (KNBK), NAME customer matching (never needed on the samples).
  - M03: both hand-written "unseen" batches were used for fixes - no fresh unseen number exists (first try was
    15/18). Add a new batch before quoting one. Spanish reply headers are not stripped by mail-parser-reply.
  - M02 deskew: OpenCV minAreaRect returns -90..0 here, so some tilted scans are not straightened (R19-0114,
    R29-0161). Owner decided: keep OpenCV, do not change for now.
  - M05: R19-0113 / R19-0115 customer not identified (unknown sender domains); payer / currency cluster flags
    stay blank until 3 past rows exist (history comes with M11); amounts in another currency score 0 for amount
    (nothing converted - TCURR conversion is planned for M07 KPIs only).
- Deferred to later modules
  - M06 follow-ups: `scripts.extract --reclean` was not run on Azure (Azure e-mails were extracted with the current
    code, so probably unnecessary); infra/main.bicep sets the image to :latest - make the tag a parameter (owner asked,
    later); the admin key is needed to call Process now (owner reads it from Key Vault in their own terminal).
  - M07: work-item API with filters / KPIs, USD conversion via TCURR, allowed actions per role.
  - M08: Knowledge Base page must use the recalculated worked example (NONE 56.4 % / NEAR 83.7 % / EXACT 95.3 %
    = max(fast path 92, formula)) - the prototype's 85.34 % does not follow raw / 0.90; fast-path text =
    "max(fast-path value, formula)". Demo login needs a demo access code (Key Vault).
  - M09: Confirm & Update SAP, Mark as Non-Duplicate (R25 "CORRECTED" advices are flagged DUPLICATE on purpose).
  - M10: link P03R / P05R payments to the earlier promise (PTP kept); ar.ptp_commitment rows are already OPEN.
  - M11: history set + live set; reset point (schema demo_reset).
- External facts
  - The Gmail app (Google, Testing mode) must be published before its token expires (~3 Nov 2026); otherwise re-run
    scripts.gmail_auth + upload.
  - The Azure free account ends ~25 Nov and is never upgraded, so the M15 snapshot must be exported while Azure still runs.
  - The Claude plan ends 17 Nov.
