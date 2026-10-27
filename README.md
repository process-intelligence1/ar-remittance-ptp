# AR Remittance & PTP Control Tower

> **Demo application with synthetic data. All rights reserved.**

End-to-end Accounts Receivable demo: customer e-mails (remittance advices and
promises to pay) arrive in a Gmail inbox, are read (text + OCR), classified,
matched to open SAP items (BSID), scored, and handled by AR users through a
web workbench with a full audit trail.

## Architecture (target)

| Layer | Local (laptop) | Demo environment (Azure) |
|---|---|---|
| Front-end (React) | `npm run dev` | Azure Static Web Apps |
| API (FastAPI) | `uvicorn app.main:app` | Azure Container Apps |
| Worker (Gmail, OCR, matching) | `python -m worker` | Container Apps Job (scheduled) |
| Database | PostgreSQL 17 | Azure Database for PostgreSQL |
| Files | `data/runtime` | Azure Blob Storage |
| Secrets | `.env` (never committed) | Azure Key Vault |
| Build & deploy | — | GitHub Actions + Bicep |

## Folder layout

```
backend/
  app/
    config.py         settings (read from .env)
    db.py             database connection
    models/sap.py     SAP reference tables (schema "sap")
    models/ar.py      app tables (schema "ar"): e-mails, invoice rows, PTP, audit, jobs, rules
    api/              API endpoints
    rules_defaults.py Knowledge Base rules (weights, thresholds)
  alembic/            database migrations (numbered table changes)
  scripts/            loaders: reference data, rules and demo users
data/
  seed/               SAP reference Excel files (BSID, customers, currencies)
  samples/emails/     sample customer e-mails used by the demo
docs/                 step-by-step guides
```

## Run locally

See `docs/DAY2_GUIDE.md` for the full, explained steps. Short version (PowerShell, from `backend`):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
python -m scripts.load_reference
python -m scripts.seed_app
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs

## Safety rules

- Secrets live outside the project folder and in `.env`, which Git ignores.
- Every outgoing e-mail is redirected to the demo inbox (`OUTBOUND_MODE=redirect`).
- SAP is simulated: "Confirm & Update SAP" moves items from `sap.bsid` to `sap.bsad`.
