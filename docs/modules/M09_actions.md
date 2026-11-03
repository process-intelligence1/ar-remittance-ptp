# M09 - Actions, Confirm & Add to Excel, Exported cases, outbound e-mail

Status: built and tested on the laptop (3 Nov 2026). NOT deployed yet; the Gmail token needs the send permission first (see "Gmail" below).

## What an analyst can do
| Action | Result (status) | Notes |
|---|---|---|
| Confirm & Add to Excel | CONFIRMED | adds the row to the export list; **no SAP change**; needs invoice no., customer and (BSID match or amount) |
| Add / Update Invoice Details, Add BSID Invoice Details | re-scored | fields: invoice no., amount, currency, payment date, payment reference, customer, company code; optionally pick the BSID item (candidates are listed only in this dialog) |
| Reject Record | REJECTED | comment required |
| Request Clarification | AWAITING_CUSTOMER | e-mail from a template in the customer's language (KNA1.SPRAS), previewed and editable; queued as job SEND_EMAIL; the worker job is started at once |
| Escalate to AR Supervisor | ESCALATED | assigned to AR_SUPERVISOR; only the supervisor can act afterwards; comment required |
| Close as Duplicate | RESOLVED | |
| Mark as Non-Duplicate | re-scored | clears the duplicate link and scores the row again |

Bulk (Action Queue): Confirm, Reject, Escalate, Close as Duplicate - **all or nothing**: if one selected row is not valid, nothing changes and the dialog lists the rows.

## Rules that matter
- **Versions.** Every action carries the row `version` it was looking at (`work_item.row_version`, bumped on every update). A stale version answers `409 "changed by someone else - refresh"`.
- **Dashboard stays decision-based.** Buckets (Auto / Manual / Exception / Duplicate) come from `decision` only (`app/charts.py bucket_of`, `frontend/src/data/charts.ts bucketOf`, shared fixture). Status-only actions never move a row. Add / Update details and Mark as Non-Duplicate calculate the row again with the normal scoring, so they can change the decision - by design.
- **Audit.** One entry per action: before / after (decision, status, confidence, match level, BSID, edited fields), comment, actor, role, business date. Exports write `EXPORTED_TO_EXCEL`.
- **Outbound safety (CLAUDE.md rule 3).** The recipient is always `OUTBOUND_REDIRECT_TO`; any `OUTBOUND_MODE` other than `redirect` is refused. Subject `[AR-DEMO][CLARIFICATION → <intended recipient>] ...`, header `X-AR-Demo: outbound`, label `AR-Outbound`.
- **Customer replies.** A reply in the same Gmail thread as a sent clarification is linked to the case (`email_message.parent_email_id`), the case's AWAITING_CUSTOMER rows go back to PENDING_REVIEW (audit `CUSTOMER_REPLIED`), and the reply is processed like any e-mail.

## Exported cases
`GET /api/exports/cases` returns ALL confirmed cases; the screen shows them Excel-style (green title bar, column letters, row numbers, gridlines, sheet tabs "Cases" and "Summary" = totals per customer and currency). "Download .xlsx" builds the file in the browser with ExcelJS (loaded only on download) and then calls `POST /api/exports/cases/mark-exported` (`exported_at` / `exported_by`; downloading again is allowed).

## Code
- Back end: `app/actions.py` (rules, bulk, export list), `app/api/actions.py` (endpoints), `app/matching/rescore.py` (re-match / re-score one row), `app/outbound.py` (templates, queue, send, replies), worker step `send_outbound`, migration `d5f2a8b3e006`. Jinja2 added to both requirement files.
- Front end: `components/ActionDialogs.tsx`, `components/ExportedCases.tsx`, `export/cases.ts`, data layer methods `performAction / performBulk / previewEmail / bsidChoices / exportedCases / markExported` (live implemented; snapshot stubs for M15).

## Endpoints
`POST /api/work-items/{id}/actions` · `POST /api/work-items/bulk-actions` · `POST /api/work-items/{id}/outbound-preview` · `GET /api/work-items/{id}/bsid-candidates?q=` · `GET /api/work-items/{id}/outbound` · `GET /api/exports/cases` · `POST /api/exports/cases/mark-exported`

## Gmail
Sending needs the `gmail.send` scope. The code already asks for `gmail.modify` + `gmail.send` (`app/gmail/client.py`). Whether the token now in Key Vault has the send scope was not checked (tokens are never read). To be sure: publish the privacy / terms pages, add the scope to the Google app, run `scripts.gmail_auth` once, upload the token (steps in the hand-over message; same renewal procedure as in CLAUDE.md).

## Tests (3 Nov 2026)
Back end 588 pass (17 new in `tests/test_actions.py`); front end 66 pass (13 new in `src/test/actions.test.tsx`, incl. reading the generated .xlsx back with ExcelJS).
Not yet checked: the screens in a real browser against a running API, real Gmail sending, the Azure deploy.
