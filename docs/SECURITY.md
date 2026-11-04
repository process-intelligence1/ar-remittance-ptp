# Security setup (demo)

This is a **demo** with synthetic data on a zero-cost cloud footprint. The setup is deliberately small; the list at the end says what a production system would add.

## What is protected, and how
| Area | Setup |
|---|---|
| **Secrets** | Never in the repository (it is public). In Azure they live in Key Vault and reach the apps through a managed identity: database URL, Gmail token, JWT signing key, demo access code, admin key. On the laptop they are in `.env` and in a folder outside the project. Secret scanning with push protection is on in GitHub. |
| **Login** | Demo users pick themselves and type the **demo access code**; the API then issues a signed token (10 hours). 10 attempts per minute per address, then a lock-out. The browser signs out after 60 minutes without activity. The demo edition (GitHub Pages) has no login secret at all: it contains only synthetic data. |
| **Admin functions** | `/api/admin/*` needs the header `X-Admin-Key` (a Key Vault secret; empty = admin switched off). Demo Control functions need a signed-in user. |
| **Least privilege in Azure** | The API's identity may start exactly one job (a custom role on that job only), read its own secrets and use the storage container. The database firewall is closed to GitHub: migrations and the history build run *inside* Azure as jobs. Key-based access to the storage account is switched off. No container registry, no public IPs, no VMs. |
| **E-mail** | Outgoing mail can only go to the owner's demo mailbox (`OUTBOUND_MODE=redirect`; any other mode is refused). The subject and the first line name the customer it would have gone to. Alerts for history records are never mailed. |
| **SAP data** | Simulated in PostgreSQL and read-only for the app. "Confirm & Add to Excel" changes only the status; the Excel file is the posting file. |
| **Audit** | Every action writes who, when, before / after and the comment (append-only). |
| **Scanning** | *Secret scan* (gitleaks) over the full git history, the files and every stored API image: runs on every push to `main`, every Monday and on demand, and **fails when it finds anything**. *CodeQL* runs on every push. Dependabot alerts are on. |

## Public repository rules
No secrets, no Azure app URL or other environment addresses, no real customer data. The samples and SAP data are synthetic. The demo edition's data is exported only from the clean `ar_snapshot` database, only for live / history samples, and must pass `scripts.check_snapshot` first (every e-mail address must be known from the samples or the SAP master data; no mailbox, host name, token or key may appear; report in `docs/reports/`).

## Accepted findings
- **Secret scan:** two public Azure built-in role ids in `infra/main.bicep` look like keys to the scanner. They are exempted by exact value and file (`.gitleaks.toml`, `.gitleaksignore`); everything else in that file is still scanned.
- **Dependencies (3 Nov 2026):** 0 critical and 0 high alerts remain in the repository (PyJWT and React Router fixed; Vite / Vitest and their dependencies upgraded to current majors). 11 moderate alerts remain, from two components: the packages inside **ExcelJS** (it is the last release; its bundled copies cannot be patched from here, and no untrusted input reaches them: the Excel file is built in the browser from the user's own cases) and **React Router 6** (the fix is version 7, a migration of the routes). Dependabot's automatic fix pull requests are off on purpose (they would open new pull requests every week for a demo that ends soon); alerts stay on.

## What a production system would add
Private networking and a web application firewall; sign-in with the company identity provider (Entra ID) and roles from it instead of an access code; key rotation and a secrets-management policy; high availability and disaster recovery; centralised logging and alerting (SIEM); vulnerability scanning of images and dependencies in the pipeline with enforced gates; penetration test; data-protection review for real customer data; real SAP and Exchange connectors with service accounts.

## Reporting a problem
Open a private security advisory on the repository (Security tab) or contact the owner. Never put a suspected secret into an issue.
