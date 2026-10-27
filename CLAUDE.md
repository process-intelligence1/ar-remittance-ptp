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
- Project folder: D:\Finance\AR_Remittance  (GitHub: process-intelligence1/ar-remittance-ptp, private)
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

## Business decisions
- One row per INVOICE (ar.work_item); several rows can belong to one e-mail.
- E-mail type when read: REMITTANCE / PTP / OUT_OF_SCOPE (an e-mail can contain both remittance
  and PTP lines). Final classification per row: REMITTANCE / PTP / DUPLICATE / EXCEPTION / OUT_OF_SCOPE.
- Scoring per Knowledge Base: weights 0.35 digit, 0.30 amount, 0.10 sender->company code,
  0.05 name, 0.10 date; raw / 0.90 = confidence %. Fast path 92% / 91%.
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
  R = remittance, P = PTP, P..R = both, O = out of scope.

## Plan status
- Day 1 done: tools installed, repo created, local database created.
- Day 2: backend skeleton, tables (Alembic), reference data loaded, first API - see docs/DAY2_GUIDE.md.
- Day 3 done (Milestone 1): API live in Azure Container Apps - see docs/DAY3_GUIDE.md.
  URL https://ar-api.reddune-37179e92.centralindia.azurecontainerapps.io . rg-ar-demo (centralindia):
  ar-api, cae-ar-demo, psql-ar-demo-snjjnahqgx3b4 (B1ms, data loaded), kv-ardemo-snjjnahqgx3b4,
  id-ar-api, log-ar-demo, policy "allowed resource types"; budget-ar-demo ($1) on the subscription.
  Azure account processintelligence1@outlook.com (Free Trial, spending limit on).
  Code deploys: push to main -> .github/workflows/deploy.yml (OIDC, environment "demo", no reviewer:
  GitHub Free). Infra deploys: .\infra\deploy.ps1 [-WhatIf] (rotates DB password each run).
  GHCR pull token must be a CLASSIC PAT (read:packages), stored only in Key Vault by the owner.
- M01 done (Gmail ingestion + sample sender) - see docs/modules/M01_gmail_ingestion.md.
  Storage account stardemosnjjnahqgx3b4 / container ar-files; Gmail token in Key Vault "gmail-token"
  (Google app in TESTING mode: token expires ~3 Nov 2026 -> re-run scripts.gmail_auth + upload).
  Container runs `alembic upgrade head` on start. Tests: `python -m pytest` in backend (275 pass).
  Whole inbox is processed (NO date cut-off) except system senders in rule "ignored_senders"
  (not stored; audit EMAIL_IGNORED + Gmail label AR-Ignored). scripts.purge_ignored removes old ones.
- Next: M02 document reading/OCR, then M03-M08 (see docs/BUILD_PLAN.md). MVP target 9 Nov 2026.
