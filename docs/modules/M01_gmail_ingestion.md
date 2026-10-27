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
- **The whole inbox is processed** (no date cut-off) — except **system senders**: rule
  `ignored_senders` in `ar.rule_config` holds **only these domains** (incl. their sub-domains):
  github.com, google.com, accounts.google.com, microsoft.com, azure.com, anthropic.com, claude.ai,
  claude.com. Their e-mails are **not stored** (no body, no files): only an audit entry
  `EMAIL_IGNORED` (date, sender, reason "ignored system sender") and the Gmail label `AR-Ignored`.
  Checked on the real From and, for forwards, the original sender.
  **No address patterns** such as `noreply@*`: automated senders can send genuine remittances —
  sample R19-0112 comes from `noreply@kangaroo-erp-mail.net` (customer 102469). Everything not on
  the domain list is stored and goes on to classification.
- **Re-fetch** (`python -m scripts.refetch_ignored`, list only; `--yes` to act): finds Gmail
  messages labelled `AR-Ignored` that the current rule no longer ignores and removes the label,
  so the next poll stores them.
- **Sample sender**: puts a sample from `data/samples/emails/<CODE>/` into the inbox with the
  **customer as sender** (Gmail "import" — nothing is e-mailed to anyone). It is dated **now**,
  so it appears at the top of the inbox; the sample's own date is kept in `X-Original-Date`
  (`--original-date` keeps the old date, for building history in M11).
- **Only Azure polls** (`POLLER_ENABLED=true` there, false on the laptop): both read the same
  inbox, and whoever polls first takes the e-mail. On the laptop `--force` overrides this.
- **Admin endpoints** (`/api/admin/*`) need the header `X-Admin-Key`; the key is Key Vault
  secret `admin-api-key`. Without a configured key they are switched off (403).

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
python -m scripts.send_sample R01-0007          # one or more codes (dated now)
python -m scripts.poll_gmail                    # refuses: the poller runs in Azure only
python -m scripts.poll_gmail --force            # poll from the laptop anyway (takes mail from Azure)
python -m scripts.purge_ignored                 # LIST stored e-mails from ignored senders
python -m scripts.purge_ignored --yes           # ... and delete them (rows + files, relabel AR-Ignored)
python -m pytest                                # 291 tests
```
Azure (in your own terminal — the key goes into a variable, it is never shown):
```powershell
$u = Read-Host "API URL (see GitHub environment "demo" / Azure portal)"
$k = az keyvault secret show --vault-name kv-ardemo-snjjnahqgx3b4 --name admin-api-key --query value -o tsv
Invoke-RestMethod -Method Post "$u/api/admin/gmail/poll" -Headers @{ "X-Admin-Key" = $k }   # poll now
Invoke-RestMethod "$u/api/emails?sample_code=R01-0007"                                     # what was stored (no key needed)
Remove-Variable k
```
Or open `…/docs`, click **Authorize**, paste the key (copy it from the Azure portal → Key Vault
→ Secrets → admin-api-key), then use "Try it out".

Results on 27 Oct 2026: laptop stored 39 inbox e-mails (incl. R01-0007 with its PNG and
R30-0165 whose ZIP contains a PDF); second poll stored 0. Azure stored R01-0007 as
EML-000001 with the identical SHA-256; second poll stored 0. After adding the ignore list,
18 already-stored system e-mails (GitHub, Google, Microsoft, Anthropic) were deleted on the
laptop (20 files) and relabelled `AR-Ignored`; 21 e-mails remain. Azure had none to delete.

To change the ignore list: edit the `ignored_senders` row in `ar.rule_config` (screens for
rules come later); the default is in `backend/app/rules_defaults.py`.

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
- Non-AR mail from senders **not** on the ignore list (e.g. personal Gmail addresses) is
  still stored; classification (M03) will mark it OUT_OF_SCOPE.
- Polling is manual (admin API, or `--force` on the laptop) until the scheduled worker in M06.
- `/api/emails` has no login yet (M08) and therefore shows metadata only — no bodies or files.
- Sample `Date:` lines have no time zone: treated as UTC (kept in `X-Original-Date`).
- Reply stripping has no Portuguese-specific rules (falls back to the general rules).
- R01-0007's attachment is a PNG (the plan said "PDF").
- E-mail numbers can skip (tests use numbers from the same sequence) — harmless.
