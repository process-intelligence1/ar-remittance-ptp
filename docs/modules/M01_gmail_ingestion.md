# M01 — Gmail ingestion and sample sender

## What it does
- **Reads the inbox** of processintelligence1@gmail.com. Every inbox e-mail without the
  Gmail label `AR-Processed` becomes one row in `ar.email_message`, and each attachment one
  row in `ar.email_attachment`. Files inside a ZIP are stored too, pointing to the ZIP
  (`parent_id`, `depth` = how deep inside ZIPs).
- **Stores the files**: the raw e-mail (`message.eml`) and every attachment, each with a
  SHA-256 fingerprint. Laptop: `data\runtime\emails\EML-…\`. Azure: Blob container `ar-files`.
- **Labels in Gmail**: `AR-Processed` after storing; our own outgoing e-mails
  (`X-AR-Demo: outbound`) get `AR-Outbound` and are skipped.
- **Sample sender**: puts a sample from `data/samples/emails/<CODE>/` into the inbox with the
  **customer as sender** (Gmail "import" — nothing is e-mailed to anyone).

## How it works
```
 data/samples/emails/R01-0007/            Gmail inbox                         PostgreSQL ar.*
   body.txt + attachments  ── send_sample ─►  (customer as sender)  ── poller ─►  email_message
                               (import)        label: INBOX, UNREAD     │          email_attachment
                                                                        │          audit_log
                                                                        ├─► storage (local / Blob)
                                                                        └─► Gmail label AR-Processed
```
- **Sender**: the real `From:`; for a manual forward ("Fwd:", Outlook "Original Message",
  German/French/Spanish/Portuguese/Japanese forward lines) the **original sender** from the
  forwarded block. The real From is kept in `from_email`, `is_forwarded = true`.
- **Clean body**: `body_text_clean` = the latest message without quoted reply history
  (library `mail-parser-reply`). For forwards it keeps the forwarder's note **and** the
  forwarded message (that is the content we need).
- **No duplicates**: `gmail_id` is unique. If storing worked but labelling failed, the next
  poll recognises the message and only labels it. Only one poll runs at a time.
- **ZIP safety**: max 3 levels deep, 200 files, 50 MB unpacked; a bad ZIP is kept as a file
  and the problem is noted in `email_message.error`.
- **Sample header**: imported samples carry `X-AR-Sample: <code>` → `source = sample`,
  `sample_code` filled in.
- **Database upgrades in Azure** now happen automatically: the container runs
  `alembic upgrade head` each time it starts.

## How to try it
Laptop (VS Code terminal, in `D:\Finance\AR_Remittance\backend`, venv active):
```powershell
python -m scripts.send_sample R01-0007          # one or more codes
python -m scripts.poll_gmail                    # read new inbox e-mails once
python -m scripts.poll_gmail                    # again: "stored 0" (no duplicates)
python -m pytest                                # 258 tests
```
Azure:
- `POST https://ar-api.reddune-37179e92.centralindia.azurecontainerapps.io/api/admin/gmail/poll` — poll now
- `GET  …/api/emails` (or `…/api/emails?sample_code=R01-0007`) — what was stored
- Or open `…/docs` and use "Try it out".

Results on 27 Oct 2026: laptop stored 39 inbox e-mails (incl. R01-0007 with its PNG and
R30-0165 whose ZIP contains a PDF); second poll stored 0. Azure stored R01-0007 as
EML-000001 with the identical SHA-256; second poll stored 0.

## One-time setup (already done)
1. Google Cloud: Gmail API enabled, OAuth client type **Desktop**, your address as test user.
2. `.env`: `GMAIL_CLIENT_SECRET_FILE`, `GMAIL_TOKEN_FILE` (both in `D:\Finance\Secret`).
3. `python -m scripts.gmail_auth` → writes the token file.
4. Upload it to Key Vault (type this yourself):
   ```powershell
   az keyvault secret set --vault-name kv-ardemo-snjjnahqgx3b4 --name gmail-token --file "D:\Finance\Secret\gmail_token.json" --output none
   ```

## Limitations
- ⚠️ **The Google app is in Testing mode → the Gmail token expires after 7 days** (about
  3 Nov 2026). Then: run step 3 and 4 again (and restart the app, or wait ≤30 min).
  Publishing to "In production" needs privacy/terms pages — planned in M08.
- The poller takes **every** inbox e-mail, including non-AR mail (GitHub, Google, receipts).
  Classification (M03) will mark these OUT_OF_SCOPE. Set `GMAIL_INGEST_SINCE=YYYY-MM-DD` to
  ignore older mail if ever needed.
- The laptop and Azure read the **same inbox**: whichever polls first takes a message (the
  label hides it from the other). Use one of them at a time.
- Polling is manual (script or API) until the scheduled worker in M06.
- `/api/admin/gmail/poll` has no login yet (M08); `/api/emails` shows metadata only — no
  bodies or files — for that reason.
- Sample `Date:` lines have no time zone: treated as UTC. Gmail sorts imported samples by
  that date, so they appear among older mail, not at the top.
- Reply stripping has no Portuguese-specific rules (falls back to the general rules).
- R01-0007's attachment is a PNG (the plan said "PDF").
- E-mail numbers can skip (tests use numbers from the same sequence) — harmless.
