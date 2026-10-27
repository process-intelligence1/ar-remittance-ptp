# Day 3 — First deployment to Azure (Milestone 1)

Result: the API runs in Azure, uses an Azure PostgreSQL database, and every push
to `main` that changes `backend/**` or `infra/**` rebuilds and redeploys it
automatically. Everything is described in code (Bicep + a GitHub workflow).

**Public URL:** not written in the repo (see GitHub environment "demo" / Azure portal: Container App `ar-api` → Application Url).

| Try it | What you should see |
|---|---|
| `/api/health` | `{"status":"ok","database":true,"environment":"demo"}` |
| `/api/reference/summary` | `bsid: 4840`, `kna1: 71`, … |
| `/docs` | the interactive API test page |

⏱️ The app **scales to zero** when nobody uses it (after ~5 minutes). The first
call after that takes **~20 seconds** while Azure starts it again. That is
normal — and it is what keeps it free.

---

## 1. What was built

All in resource group **`rg-ar-demo`**, region **Central India**, tagged
`project=ar-demo`, `cost=free-tier`.

| Name | What it is, in plain words |
|---|---|
| `ar-api` | **Container App** — runs our FastAPI backend. 0 to 1 copies, ¼ CPU, ½ GB memory. HTTPS only. |
| `cae-ar-demo` | **Container Apps environment** — the "building" the app lives in. Consumption (pay-per-use) only. |
| `psql-ar-demo-snjjnahqgx3b4` | **PostgreSQL 17** server, size B1ms (smallest), 32 GB, 7-day backups. Database `ar_demo`. |
| `kv-ardemo-snjjnahqgx3b4` | **Key Vault** — the safe. Holds `database-url`, `gmail-token` and `admin-api-key` (the GHCR pull token was removed when the image became public). |
| `id-ar-api` | **Managed identity** — the app's "staff badge" for opening the Key Vault. No password. |
| `log-ar-demo` | **Log Analytics** — stores the app's logs. Hard cap 0.1 GB per day, kept 30 days. |
| `ar-demo-allowed-resource-types` | **Azure Policy** — Azure refuses to create any other kind of resource in this group (no VMs, no container registry, no public IPs, …). |
| `budget-ar-demo` | **Budget** ($1/month, on the subscription) — e-mails processintelligence1@outlook.com at 50 % / 100 % actual and 100 % forecast. |

Outside Azure resources:

| Where | What |
|---|---|
| Entra ID | App registration `gh-ar-remittance-ptp-deploy` — the identity GitHub Actions uses. **Contributor on `rg-ar-demo` only.** Signs in with a *federated credential* (OIDC): Azure trusts tokens from this repo's `demo` environment; there is no password/secret. |
| GitHub | Environment `demo` (only branch `main` may deploy). Secrets `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` (IDs, not passwords). |
| GitHub Container Registry | Private image `ghcr.io/process-intelligence1/ar-api` (tags: commit SHA + `latest`). |

Files in the repo:

| File | Purpose |
|---|---|
| `backend/Dockerfile`, `backend/.dockerignore` | Recipe for the container image (Python 3.12 slim, non-root user, port 8000). |
| `infra/main.bicep`, `infra/main.parameters.json` | Everything in `rg-ar-demo`, as code. |
| `infra/policy/allowed-types.bicep` | The "allowed resource types" guard rail. |
| `infra/deploy.ps1` | Preview (`-WhatIf`) or deploy the infrastructure from the laptop. |
| `.github/workflows/deploy.yml` | Build → push image → roll out to Azure → health check. |
| `.gitattributes` | Linux line endings for files that run in Linux. |

## 2. How the pieces connect

```
  You (VS Code)                          GitHub
  ─────────────                          ──────────────────────────────────────────
  git push main ───────────────────────► Actions: "Build and deploy API"
                                           1. build image ──► ghcr.io/.../ar-api:<sha>
                                           2. sign in to Azure with OIDC (no secret)
                                           3. az containerapp update --image :<sha>
                                           4. call /api/health
                                                   │
  Azure  rg-ar-demo (Central India)                ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  Container Apps environment (Consumption)                                │
  │   ┌──────────────────────┐   pulls image with token    ghcr.io (GitHub)  │
  │   │  ar-api  (0..1 copy) │ ◄────────────────────────── private image     │
  │   │  FastAPI :8000       │                                               │
  │   └──┬──────────┬────────┘                                               │
  │      │ HTTPS    │ reads secrets as id-ar-api                             │
  │      │          ▼                                                        │
  │      │   ┌──────────────┐  database-url, gmail-token, ...                │
  │      │   │  Key Vault   │                                                │
  │      │   └──────────────┘                                                │
  │      │ DATABASE_URL (TLS)                                                │
  │      ▼                                                                   │
  │   ┌─────────────────────────────┐   firewall: Azure services             │
  │   │ PostgreSQL 17 B1ms  ar_demo │            (+ your laptop IP, optional)│
  │   └─────────────────────────────┘                                        │
  │   Log Analytics (0.1 GB/day cap) ◄── app + platform logs                 │
  │   Policy: only these resource types allowed                              │
  └──────────────────────────────────────────────────────────────────────────┘
        ▲
        │ https://<ar-api URL - see GitHub environment "demo" / Azure portal>
   Browser / front-end (later)
```

**Two kinds of change, two ways to deploy:**

- **Code change** (`backend/**`): just push. GitHub builds and rolls out.
- **Infrastructure change** (`infra/*.bicep`): run from the repo folder
  ```powershell
  .\infra\deploy.ps1 -WhatIf      # preview first, always
  .\infra\deploy.ps1              # then deploy
  ```
  The script makes a **new random database password** every run, sends it
  straight to Azure (server + Key Vault), never prints or saves it, and restarts
  the app so it uses the new one. Add `-NoClientIp` if you don't want your laptop
  IP in the database firewall.

**Running database scripts against Azure from the laptop** (only when needed;
your laptop IP must be in the firewall — run `.\infra\deploy.ps1` without
`-NoClientIp` first):
```powershell
cd D:\Finance\AR_Remittance\backend
$env:DATABASE_URL = az keyvault secret show --vault-name kv-ardemo-snjjnahqgx3b4 --name database-url --query value -o tsv
.\.venv\Scripts\python.exe -m alembic upgrade head
Remove-Item Env:DATABASE_URL     # forget it again
```
*The value lives only in this terminal's memory; close the terminal and it is gone.*

## 3. What it costs

Subscription: **Azure free account** (`FreeTrial`, spending limit **On**).

| Item | Free allowance | Our use | Cost |
|---|---|---|---|
| Container App | 180,000 vCPU-seconds + 360,000 GiB-seconds + 2 M requests per month | ¼ CPU ⇒ about **200 hours awake per month** free; idle = 0 copies = nothing used | $0 |
| Container Apps environment | Consumption plan has no base fee | — | $0 |
| PostgreSQL B1ms + 32 GB | **750 hours/month + 32 GB storage + 32 GB backup, for 12 months** (free account) | 1 server, always on | $0 for 12 months |
| Log Analytics | 5 GB/month | capped at 0.1 GB/day (≤ 3.1 GB/month) | $0 |
| Key Vault Standard | no free tier; $0.03 per 10,000 operations | a few reads per hour | well under $0.01/month (paid from the free credit) |
| Managed identity, roles, policy, budget, Entra app | always free | — | $0 |
| GitHub Actions (private repo) | 2,000 minutes/month | ~2–3 min per push | $0 |
| GitHub Packages (private) | 500 MB storage | one small image + its old versions | $0 |

## 4. Cost risks to watch

1. **PostgreSQL is free for 12 months only.** After that, B1ms is roughly
   $13–15/month. Before the 12 months end: delete it or ask for a plan.
2. **Free trial ends after 30 days (or when the $200 credit is used).** To keep the
   12-month free services you must *upgrade* to Pay-As-You-Go. Upgrading
   **removes the spending limit** — from then on, the **$1 budget e-mail** is
   your alarm. Check the inbox of processintelligence1@outlook.com.
3. **Never stop/start things "to save money" by changing sizes.** Bigger
   PostgreSQL sizes, more replicas or more CPU are not free. The policy blocks
   new resource *types*, but not bigger sizes of allowed types.
4. **Logs:** the 0.1 GB/day cap protects you; if logs stop appearing late in the
   day, that's the cap working (it resets daily).
5. **GHCR storage:** every push adds an image version. If the package nears
   500 MB, delete old versions (GitHub → your profile → Packages → ar-api →
   Package settings / versions).
6. **Where to look:** Azure portal → *Cost Management → Cost analysis*
   (scope: Azure subscription 1) and *Budgets*.

## 5. Things to remember

- **GHCR pull token: no longer used.** Since the repo and the image are public, Azure pulls
  `ghcr.io/process-intelligence1/ar-api` without credentials (the token and its Key Vault secret
  were removed). History: it had to be a *classic* token with `read:packages`.
- **No approval step:** GitHub Free can't require a reviewer on a private repo,
  so every push to `main` deploys. Only `main` can deploy to `demo`.
- **The app currently uses the PostgreSQL admin login.** A separate, smaller
  app user is planned for later.
- **First deployment needed two passes** (`.\infra\deploy.ps1 -SkipApp`, store the
  token, then `.\infra\deploy.ps1`), because the app reads the token from Key
  Vault while it is being created. Re-runs need one pass.

## If something fails

| Symptom | Likely cause / fix |
|---|---|
| First call takes ~20 s | Normal: scaling up from zero. |
| URL times out for minutes, app "Unhealthy" | Check logs: Azure portal → `ar-api` → *Log stream* / *Logs*. "ImagePullUnauthorized" ⇒ the GHCR token is wrong/expired (see above). |
| `/api/health` says `"database": false` or 500 error | Database password/secret mismatch — run `.\infra\deploy.ps1` again (it resets both). |
| Workflow: "No matching federated identity record" | The repo was renamed/moved; the federated credential subject must match the one in the error. |
| Laptop scripts can't connect to the database | Your IP changed; run `.\infra\deploy.ps1` (adds the current IP). |
