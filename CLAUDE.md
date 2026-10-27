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
  (B1ms), Blob Storage, Key Vault, Static Web Apps, Entra ID login, App Insights. Deployed by GitHub
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
  0.05 name, 0.10 date; raw / 0.90 = confidence %. Fast path: EXACT + BSID open + same currency +
  amount within 2% = 92%; EXACT + amount missing = 91%.
  >=80 + BSID = Auto Process; >=80 no BSID = Exception; 40-79 Manual Review; <40 Manual Investigation.
  Rules live in ar.rule_config (defaults in backend/app/rules_defaults.py).
- Payments without invoice numbers: find open invoices summing to the amount; always send to review.
- Demo "business date" (default 2026-10-28) is used by all rules instead of the real date.
- Payer/currency cluster: same customer's past items in the same currency from the same sender
  domain; leave blank when there is not enough history.
- Roles: AR_ANALYST, CASH_APPLICATION, COLLECTIONS_ANALYST, AR_SUPERVISOR.
- Demo Control page: Reset demo (restores snapshot with ~200 history e-mails incl. actions per
  invoice), Send sample e-mail (Gmail import with the customer as sender), Upload sample, Process now,
  business date. ~35 samples held back for live sending.

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
  Code deploys: push to main -> .github/workflows/deploy.yml (OIDC, environment "demo", no reviewer:
  GitHub Free). Infra deploys: .\infra\deploy.ps1 [-WhatIf] (rotates DB password each run).
  Image ghcr.io/process-intelligence1/ar-api is PUBLIC: no GHCR pull token (removed from Bicep + Key Vault).
- M01 done (Gmail ingestion + sample sender) - see docs/modules/M01_gmail_ingestion.md.
  Storage account stardemosnjjnahqgx3b4 / container ar-files; Gmail token in Key Vault "gmail-token"
  (Google app in TESTING mode: token expires ~3 Nov 2026 -> re-run scripts.gmail_auth + upload).
  Container runs `alembic upgrade head` on start. Tests: `python -m pytest` in backend (366 pass).
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
  Tesseract + 7 languages; workflow keeps only the 3 newest GHCR versions (500 MB free limit).
  OCR in Azure: only 1-2 test files on the API container until the M06 worker.
- M03 done (classification) - see docs/modules/M03_classification.md and
  docs/reports/M03_classification_report.md. app/classification/: keyword rules (EN/DE/FR/ES/PT/JA,
  lexicons.py) + small TF-IDF/logistic-regression model asked below 70 % confidence. Settings in
  ar.rule_config "classification". Samples 234/234 (rules, and rules + model cross-validated); new
  hand-written wording first try 15/18 (data/eval/classification_unseen.json - both batches since used
  for fixes). scikit-learn is LAPTOP-ONLY (requirements-dev.txt, training); the image predicts with numpy
  from app/classification/model.npz because GHCR is at ~491/500 MB. Retrain: scripts.train_classifier.
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
- Next: M04 extraction, then M05-M08 (see docs/BUILD_PLAN.md). MVP target 9 Nov 2026.
