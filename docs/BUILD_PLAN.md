# Build Plan — module by module

Read together with `CLAUDE.md` (project rules, decisions, zero-cost constraints).
Days 1–3 are done: tools, repo, local DB, backend skeleton, SAP reference data, first Azure
deployment (Container App `ar-api`, PostgreSQL B1ms, Key Vault, Log Analytics, policy,
GitHub Actions with OIDC). Inspect the existing `infra/`, `.github/workflows/` and `backend/`
before changing them — extend, don't rebuild.

Reference material in the repo:
- `docs/prototype/AR_Remittance.html` — the HTML prototype (screens, fields, Knowledge Base text).
  Large file: search it (e.g. for section headings) instead of reading it whole.
- `data/seed/*.xlsx` — SAP reference data (already loaded).
- `data/samples/emails/<CODE>/` — 234 sample e-mails: `body.txt` (From/Subject/Date header lines,
  then the body) + attachments (pdf, docx, xlsx, csv, png, jpg, tif, zip).
  Folder prefix = expected type: `R` remittance, `P` PTP, `P..R` PTP + remittance, `O` out of scope.

---

## Standard workflow for EVERY module

1. **Plan**: read this module's section, inspect the relevant code, then show me a short plan
   (files to add/change, new libraries, any Azure change, any manual step for me). Wait for "go".
2. **Build** in small steps. New Python libraries go in `backend/requirements.txt` with pinned versions.
   Database changes only via a new Alembic migration.
3. **Test**: add `pytest` tests under `backend/tests/` for the module's logic; run them all.
   Run the module locally against the laptop database and show me real results on sample e-mails.
4. **Done-when checks**: go through this module's checklist and report each item ✅/❌.
5. **Commit** with a clear message. **Ask me before `git push`** (push = auto-deploy to Azure).
   After the deploy, verify the same thing works on the Azure URL.
6. **Document**: write `docs/modules/MXX_<name>.md` in plain language (what it does, how it works,
   how to try it, limitations) and update the "Plan status" section of `CLAUDE.md`.
7. **Summarise** for me in under 15 lines: what works, how to see it, what I need to check/do.

General rules: explain each command in one plain sentence; ask before anything that creates,
changes or deletes Azure resources (show `what-if` first and confirm it's free-tier); keep every
Azure change in Bicep; keep the Azure Policy allowed-types list in step with new resource types;
never read `.env` or `D:\Finance\Secret`, never print secrets — when a secret is needed, give me
the exact command to run myself in a separate terminal (use `Read-Host` + right-click paste, or
`--file` paths I type).

---

## MVP scope (target 9 Nov 2026)
M01 → M08 plus the simple demo login in M08. After that: M09 → M14.

---

## M01 — Gmail ingestion and sample sender
**Goal:** e-mails in processintelligence1@gmail.com become rows in `ar.email_message` /
`ar.email_attachment`; presenters can drop sample e-mails into the inbox with the customer as sender.

- `app/gmail/client.py`: OAuth (Desktop client, scopes `gmail.modify` + `gmail.send`). One-time
  consent on the laptop via a script `python -m scripts.gmail_auth` that writes the token to
  `GMAIL_TOKEN_FILE` (outside the repo). Claude never opens either file.
- Poller: fetch inbox messages without label `AR-Processed`, skip anything with label
  `AR-Outbound` or header `X-AR-Demo: outbound`. Store the raw `.eml` + every attachment
  (unpack ZIPs recursively; children point to the ZIP via `parent_id`) through a storage layer
  `app/storage.py` with two backends: `local` (folder) and `azure_blob`. SHA-256 for each file.
  Then add Gmail labels `AR-Processed` (+ later the classification label).
- Idempotent: the same Gmail message is never stored twice (unique `gmail_id`).
- Sender: real `From:`; if the mail is a manual forward, take the original sender from the
  forwarded header block in the body.
- Reply stripping: `body_text_clean` without quoted history (`email-reply-parser` or equivalent).
- **Sample sender** `app/gmail/sample_sender.py`: build an RFC 822 message from
  `data/samples/emails/<CODE>/` (From/Subject/Date from `body.txt`, attachments added) and put it in
  the inbox with Gmail `users.messages.import` (labels INBOX + UNREAD), keeping the customer as sender.
  CLI: `python -m scripts.send_sample R01-0007` and `--all-live` (the held-back live set, see M11).
- Azure: Storage account (Standard_LRS, hot, no GRS) + container `ar-files`; Gmail token in
  Key Vault (I upload it myself with a command you give me); the API's identity gets
  "Storage Blob Data Contributor" and "Key Vault Secrets User".
- **Manual steps for me (give exact instructions):** Google Cloud → OAuth consent screen
  → publish the app to "In production" (avoids 7-day token expiry); run `scripts.gmail_auth`;
  upload the token file to Key Vault.

**Done when:** sending R01-0007 via the sample sender shows it in Gmail with the customer as sender;
the poller stores it with its PDF; running the poller twice creates no duplicates; a ZIP sample
(R30-0165) stores its inner files; tests pass.

## M02 — Document reading and OCR
**Goal:** every attachment and body has clean text + tables + word positions.

- `app/documents/`: router by type → PDF with text layer (PyMuPDF + pdfplumber tables),
  scanned PDF / PNG / JPG / TIF (OpenCV deskew/denoise → Tesseract with language packs
  eng+deu+fra+spa+por+jpn+jpn_vert), DOCX (python-docx incl. tables), XLSX/CSV (openpyxl/pandas).
- Output stored in `email_attachment.text_content`, `layout` (JSON: pages, words with
  bounding boxes, tables), `parse_method`, `ocr_confidence`, `language`.
- Optional switch `OCR_ENGINE=azure_di` (Document Intelligence **F0** only) — implement the
  interface, leave it off by default.
- Docker image: add `tesseract-ocr` + the language packs; keep the image as small as possible.
- Memory: process one document at a time; downscale very large images.

**Done when:** all 234 samples parse without crashing (report a table: type, method, characters,
OCR confidence); spot-check 5 scanned files and 2 Japanese ones; image builds and deploys.

## M03 — Classification
**Goal:** each e-mail → `REMITTANCE` / `PTP` / `OUT_OF_SCOPE`, flags `contains_remittance`,
`contains_ptp`, out-of-scope category (marketing, customer service, sales inquiry, general,
vendor invoice, HR, bank notification).

- Rules first: multilingual keyword lexicons (EN/DE/FR/ES/PT/JA), attachment names, presence of
  amounts/invoice refs/promise dates, sender known in ADR6. Then a small scikit-learn model
  (TF-IDF + logistic regression) trained on the samples for low-confidence cases.
- Store `reasons` (which signals fired) for the UI.
- Evaluation script `python -m scripts.evaluate --stage classification`: accuracy vs folder
  prefixes, confusion matrix, list of misses.

**Done when:** ≥95 % accuracy on the samples (report it honestly; explain misses);
mixed e-mails (P03R, P05R, P06) flagged as containing both.

## M04 — Extraction and normalisation
**Goal:** structured header + lines from body and attachments.

- Header: payer name, sender domain, payment reference (PAY…, ZA-…, PV…, RA-2026-…, REM-…),
  payment date, total, currency. Lines: invoice ref (raw + normalised), amount, gross,
  deduction + reason (e.g. TDS), credit note flag, promise date, instalments (P08).
- Reference patterns from BSID `XBLNR` shapes (8-digit, `AAA/9999/99999`, `AA-9999999`,
  `AA-99-999999`, `AA9999-99999`, `AAA-999999`, 10-digit). Normalise both sides the same way.
- Locale-aware amounts (`15.999,58`, `₹4,19,733.30`, `¥1,234`, KWD 3 decimals) and dates
  (`dateparser`); currency symbols → ISO (S$→SGD, ₹→INR, €→EUR, ¥/円→JPY, £→GBP).
- Every value keeps its evidence (source = body/attachment id, page, bounding box) for highlighting.
- Optional, off by default: `LLM_PROVIDER=none|gemini|groq` (free tiers) fallback for e-mails the
  rules can't parse — interface only, never required.

**Done when:** evaluation report per scenario code (R01…R32, P01…P08) with extraction hit-rate
(invoice ref found and exists in BSID; amount matches BSID within 2 %); overall ≥85 % on
referenced remittances; list of failures by scenario.

## M05 — Customer identification, BSID matching, scoring, duplicates
**Goal:** one `ar.work_item` per invoice with BSID match, scores, decision and status.

- Customer: sender e-mail/domain → ADR6 → KNA1 → KNB1 (company codes); fallback fuzzy name
  (rapidfuzz, NAME1/NAME2) and bank details (KNBK).
- Candidates: open BSID items of that customer by XBLNR/BELNR/VBELN/ZUONR/XREF1–3;
  store all in `ar.match_candidate` with component scores.
- Score exactly per Knowledge Base, reading weights/bands/thresholds from `ar.rule_config`
  (fast path 92/91; normalise raw/0.90). Decision + status + recommended action per KB table.
- Duplicates: same invoice, customer, amount (±0.01 %), currency, sender domain within 7 days,
  or same attachment SHA-256 → `DUPLICATE`, `duplicate_of_id` set.
- No BSID match → `EXCEPTION` ("No BSID match found").
- Unreferenced payments (R12, R13, R28): subset-sum over the customer's open items within
  tolerance (max 6 invoices) → rows created, always `PENDING_REVIEW`.
- Payment block (`ZLSPR = R`) → always review. Credit notes (`SHKZG = H`) netted.
- Payer/currency cluster flags from history (blank when not enough history).
- Uses `business_date` from rule_config for date scoring.

**Done when:** unit test reproduces the KB worked example (with the /0.90 normalisation);
evaluation report: decision distribution per scenario; JP-26-002271 (P03-0193) matches
customer 102419 / SGD 8,300; a re-sent sample becomes DUPLICATE.

## M06 — Pipeline and worker
**Goal:** e-mails flow end to end automatically.

- `app/pipeline.py`: email → parse (M02) → classify (M03) → extract (M04) → match (M05) → audit.
  Each stage idempotent; failures recorded on the e-mail and retried via `ar.job` (max 3).
- `app/worker.py`: `--once` (poll Gmail, process queued jobs, PTP checks) and loop mode locally.
- Azure: Container Apps **Job** on a 5-minute schedule, 0.5 vCPU / 1 GiB, same image,
  `python -m app.worker --once`; keep monthly usage inside the free grant (show the maths).
- API endpoint `POST /api/admin/process-now` queues an immediate run.
- Every stage writes `ar.audit_log` entries (actor "system").

**Done when:** a sample sent via M01 appears as processed work items without manual steps, both
locally and in Azure; a forced failure is retried and visible.

## M07 — Workbench API
**Goal:** everything the screens need.

- `GET /api/work-items` (filters: dates, classification, BSID match, status, confidence,
  customer, company code, region; paging; sorting), `GET /api/work-items/{id}` (e-mail,
  attachments with download links, extraction evidence, candidates, scores, audit trail).
- `GET /api/kpis` and chart endpoints matching the prototype Dashboard (totals, AI-processed,
  manual, duplicates, exceptions, distributions by customer/region/company code, monthly trend,
  performance stability = daily auto-processing rate and average confidence). Amounts
  converted to USD via TCURR at each row's date.
- `GET /api/audit` with the prototype's filters. `GET /api/attachments/{id}/file`.
- Server-Sent Events `/api/stream` for "new rows arrived".
- Role-aware: every response says which actions the current user may take on each row.

**Done when:** OpenAPI page shows all endpoints; tests for filters and KPIs; response times
< 1 s on the full history set.

## M08 — Front-end (MVP) and demo login
**Goal:** the prototype, working against the API.

- `frontend/`: React + Vite + TypeScript. **Reuse the prototype's CSS (design tokens, layout,
  cards, badges, tables, modals) so it looks the same**; TanStack Query + Table; Chart.js.
- Screens: Dashboard, Action Queue (one row per invoice; column picker, filters, bulk select),
  Record Detail (original e-mail + attachment viewer with highlighted evidence beside the
  extracted fields; candidates and score breakdown; action buttons; audit timeline),
  Audit Trail, Knowledge Base (content from the prototype), Demo Control placeholder.
- Remove the mailbox filter; company codes 1000–6000; region from BSID `XREF2`.
- Demo login: pick one of the four demo users → API issues a JWT (signing key in Key Vault);
  buttons shown per role. (Entra ID comes in M12.)
- Azure: Static Web Apps **Free** tier; GitHub Actions builds and deploys it; API CORS updated.

**Done when:** all five screens work on the Azure URL with live data; new sample e-mail appears
in the Action Queue without refresh; works on a 1366-px laptop screen.

**→ MVP reached. Switch deployments to the manual "Run workflow" button (see CLAUDE.md).**

## M09 — Actions, simulated SAP update, outbound e-mail
- Actions per KB table: Confirm & Update SAP, Change / Add details, Reject, Request
  Clarification, Escalate to AR Supervisor, Close as Duplicate, Mark as Non-Duplicate; bulk actions.
- Confirm & Update SAP: full payment → move BSID row to BSAD with AUGDT (business date) and a
  generated AUGBL; short payment → reduce open amount, keep the rest open (no discounts).
- Outbound e-mails from Jinja2 templates in the customer's language (KNA1.SPRAS), sent via Gmail
  API **only to processintelligence1@gmail.com**, subject `[AR-DEMO][<kind> → <intended recipient>]`,
  header `X-AR-Demo: outbound`, label `AR-Outbound`; analyst previews/edits before sending.
- Customer replies (same thread) attach to the same e-mail case and trigger re-processing.
- Every action → audit log with before/after values.

## M10 — PTP engine
- `ar.ptp_commitment` per invoice/instalment; daily check (business date): paid → KEPT,
  partly → PARTIALLY_KEPT, not paid by promise + grace (3 days) → BROKEN → alert to Collections,
  escalate to Supervisor after 2 more days.
- PTP Tracker screen: upcoming / due / kept / broken, per-customer reliability.

## M11 — Demo Control and history
- Choose ~35 samples covering every scenario code as the **live set**; the rest = **history**.
- `scripts.build_history`: process the history set with business dates spread over the previous
  3 months, then play out realistic actions (confirm, reject, edit, clarifications, PTP kept/broken)
  by the four demo users so every invoice has an action trail.
- Snapshot: copy `ar.*` and `sap.bsid`/`sap.bsad` into schema `snap`; **Reset demo** = truncate +
  restore from `snap` (seconds, no external tools).
- Demo Control page: Reset demo, Send sample (pick from live set), Upload sample (zip/folder in the
  same format → added to the library in Blob storage), Process now, business date (+N days),
  link a sender address to a customer.

## M12 — Enterprise login (Entra ID)
- App registrations (free): SPA (MSAL in React) + API; app roles = the four roles; API validates
  Entra tokens; keep demo login available behind a setting for presenters without accounts.

## M13 — Hardening and governance
- Budget-triggered auto-stop (Action Group → free automation that scales the API/Job to 0 and stops
  PostgreSQL); Defender for Cloud free CSPM secure score; Dependabot; Trivy image scan in CI;
  App Insights dashboards (requests, failures, processing times); Log Analytics cap check;
  manual deploy gate; health probes; backup/restore drill for the database.

## M14 — Accuracy, presenter pack
- Evaluation dashboard page (classification + extraction + match accuracy per scenario, from the
  golden set built by analyst confirmations); presenter runbook (`docs/PRESENTER_RUNBOOK.md`);
  architecture slide content incl. "what production would add" (private networking, HA/DR,
  real SAP and Exchange connectors).
