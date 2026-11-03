# M10 - PTP engine (lean)

Status: built and tested on the laptop (3 Nov 2026). Not deployed until pushed and approved.

## What it does
`app/ptp.py` checks every promise to pay (`ar.ptp_commitment` = one invoice or one instalment) **at the business date**, never the real date.
Deadline = promise date + `grace_days` (rule `ptp`, 3). Result per promise:

| Situation | Status |
|---|---|
| paid in full (within the 2 % matching tolerance, rule `fast_path.amount_tolerance_pct`) | KEPT |
| paid in part | PARTIALLY_KEPT |
| nothing paid, business date > deadline | BROKEN, e-mail alert to Collections (once) |
| nothing paid, business date > deadline + `escalate_after_days` (2) | ESCALATED, e-mail to the AR Supervisor (once) |
| otherwise | OPEN |
| the promise record was rejected | CANCELLED |

## "Paid"
A REMITTANCE row for the same invoice or open item (same BSID item, or same normalised invoice number and customer), in any status **except REJECTED, DUPLICATE and IGNORED**, with a payment date (else the e-mail date) on or before the business date and within the deadline. A late payment (after the grace period) does not rescue a broken promise. This is also how P03R / P05R payment advices (no promise in their text) are linked to the earlier promise: they match by invoice.
- **Currency:** a payment in another currency is converted into the promise currency with the SAP rate valid at the payment date (`sap.tcurr`, via `app/fx.py`). No rate = the promise stays OPEN with a note and no alert.
- **Instalments:** several promises for one invoice share the payments, filled in promise-date order; a payment is never used twice.
- **No amount in the payment e-mail:** taken as paid in full, with a note.

## Alerts
Through the normal outbound mechanism (`app/outbound.py`): always only to `OUTBOUND_REDIRECT_TO`, subject `[AR-DEMO][ALERT → Collections] ...` / `[AR-DEMO][ESCALATION → AR Supervisor] ...`, the intended recipient (the Collections / Supervisor demo user) named in the subject and body. **Once per promise and event** (`alerted_at`, `escalated_at`); they stay set when the date is moved back, so nothing is sent twice. A promise that jumps straight past the escalation date sends both mails once. In the app: status badges, the Alerts column and the status filter of the PTP Tracker, and one audit entry per status change (`entity_type ptp`, actions `PTP_BROKEN`, `PTP_ESCALATED`, `PTP_KEPT`, ...).

## Where it runs
- The worker: every round (`app.worker`), then the alerts it queued are sent in the same round.
- `POST /api/ptp/run` (signed-in user): same check, safe to repeat; the M11 "move the date forward" demo calls it after changing the business date. The "Re-check now" button of the PTP Tracker uses it.
- `GET /api/ptp`: list with status counts, deadline, days overdue, payments found, alert flags.

## Code
Back end: `app/ptp.py`, `app/api/ptp.py`, worker step `ptp_checks`, migration `e7a4b9c1f007` (payments, broken_on, alerted_at, escalated_at, check_note, last_checked_on), `outbound.queue_message(intended=...)` (internal alerts never join a customer's e-mail thread). Front end: `pages/PtpTracker.tsx`, data layer `ptpList / runPtpChecks` (snapshot stubs for M15).

## Tests (3 Nov 2026)
Back end 606 pass (17 new in `tests/test_ptp.py`); front end 71 pass (4 new in `src/test/ptp.test.tsx`).
Checked in the browser against a local API with the business date moved to 27 Nov: 7 promises -> 5 Escalated, 1 Broken, 1 Open; the P03R-0194 sample payment advice (ingested locally) made the P03-0193 promise Kept; a second run sent no further alerts. Not checked: real Gmail delivery of the alert e-mails.
