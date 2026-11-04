# M11 - Demo Control and history

Status: built, tested, deployed (ce09dca) and the history built in Azure on 3 Nov 2026 (job ar-history: 187 e-mails in 254 s, 440 actions on 417 rows, 262 exported; promises 7 kept / 6 broken / 9 escalated / 33 open / 3 cancelled across all promises; reset point = 505 work items, 234 e-mails). Still to check: the live Demo Control page and one Reset, by the owner.

## What a presenter gets
Page **Demo Control** (any signed-in demo user):
- **Business date:** +1 / +3 / +7 / +30 days, an exact date, or back to the default. Moving it runs the promise check at once (the Promise Status column of the Action Queue, alert and escalation e-mails to the demo mailbox) and starts the worker so the e-mails go out.
- **Send a sample e-mail:** the 47 live-set samples (first sample of every scenario code; P03 + P03R and P05 + P05R kept together). The sample goes into the Gmail inbox with the customer as sender (`POST /api/demo/send-sample`), optionally with "Start processing right away". The page remembers what was sent.
- **Process now:** starts the worker job.
- **Reset demo** (with a confirmation dialog): back to the saved starting point.

## Reset point and Reset demo (`app/demo.py`)
- Schema `demo_reset` (migration `f8b5c2d0a008`) holds a copy of every `ar.*` table (not the job queue) and of `sap.bsid` / `sap.bsad`, plus a `meta` row (time, alembic revision, row counts, sequences, SAP fingerprint).
- Reset = one transaction: TRUNCATE `ar.*`, refill from the copy in foreign-key order. Everything the demo changes lives in `ar.*`, so it all comes back: work-item statuses and comments, the exported-cases list (`confirmed_at`, `exported_at`), PTP statuses and alert flags, outbound e-mails, audit entries, the sent-sample markers (`ar.demo_sample_sent`) and the business date (`ar.rule_config`). The job queue is emptied.
- Sequences are never moved back, so entry numbers and e-mail numbers are not reused. Columns added after the reset point get their default; dropped ones are ignored. SAP tables are restored only if a fingerprint (count, sum of ids and amounts) differs. A reset is refused while a job runs (RUNNING < 15 min) and while another reset runs.

## The history (`app/history.py`, `scripts/build_history.py`)
- 187 history samples (everything not in `data/samples/live_set.txt`) become e-mails with `source = 'history'`, dated on working days spread over the 3 months before the business date, in sample-number order, and go through the normal pipeline (read, classify, extract, match) under a process-local business date (`override_business_date`, nothing is stored: the live system is not disturbed). Promise and payment dates move with the e-mail.
- Then the four demo users work every in-scope row (deterministic dice by sample code and line): confirm, correct an OCR misread and confirm, reject, clarify (customers reply to most), escalate (only where the Knowledge Base offers it), close as duplicate, mark non-duplicate; about 70 % of confirmed rows were "downloaded to Excel". Every audit entry and record time is in the past. Every in-scope invoice ends with at least one user action.
- History promises are checked at the business date; their alert flags are set **without any e-mail** (history e-mails never send mail), clarifications in history are stored as already sent (no job), and the worker never picks history e-mails up.
- Resumable and additive: finished e-mails and rows are skipped; nothing is deleted; new numbers come from the normal sequences. **The reset point is taken only when everything finished** (at most 3 failed samples, no row without a user action, inside the time budget); otherwise the exit code is 3 and no reset point exists.
- Laptop result (3 Nov 2026): 187 e-mails in 2 minutes, 440 actions on 417 rows, 261 exported, promises 7 kept / 6 broken / 8 escalated / 19 open / 3 cancelled; reset point taken. `python -m scripts.drop_history` (laptop only, refuses in Azure) removes it for a new try.

## Samples in Azure
The images do not contain the samples (42 MB). `app/gmail/sample_library.py` reads them from the local folder, or - when it does not exist - from the Blob container under `samples/` (same layout: `samples/emails/<CODE>/...`, `samples/live_set.txt`). Needed for Send sample (live set) and for the history job (history set).

## Azure steps (done 3 Nov 2026; kept as the runbook)
1. Push, approve the newest deploy run (it runs migration `f8b5c2d0a008`).
2. Upload the samples to Blob: `az storage blob upload-batch --account-name stardemosnjjnahqgx3b4 -d ar-files -s data/samples --destination-path samples --auth-mode login --overwrite true` (42 MB, 423 files). Key access is off on the account and the owner needs the role Storage Blob Data Contributor (added in Bicep as `ownerBlob`; the run of deploy.ps1 in step 3 creates it - so do step 3 first).
3. `.\infra\deploy.ps1 -NoClientIp -ImageTag <sha>`: creates the one-off Container Apps job **ar-history** (full worker image, `python -m scripts.build_history`, manual trigger, 1 vCPU / 2 GiB, 3600 s, no schedule). What-if on 3 Nov 2026: 1 resource to create (ar-history), the rest is the known Bicep noise; as always the script rotates the database password, restarts the API and drops the harmless `TOKEN_REFRESHED_AT` setting.
4. `az containerapp job start -n ar-history -g rg-ar-demo` and watch its logs. Expect about 30-40 minutes with OCR (the laptop needs 2 minutes because parsing is reused); if it stops out of time it exits 3 - start it again, it continues. At the end it prints `RESET POINT taken`.
5. Check Demo Control (reset point shown), then Reset once to see it work.
The history is additive: the e-mails and rows already in Azure stay, and are part of the reset point.

## Tests (3 Nov 2026)
Back end 628 pass (39 new: `tests/test_demo.py`, incl. reset of statuses, exports, promises, alert flags, sent markers and the date); front end 77 pass (6 new). Checked in the browser against the local system: Demo Control page, +30 days (31 promises changed, only the non-history ones e-mailed), confirm a record, Reset (everything back, exported 357 to 356). Not checked: sending a sample into real Gmail (it would put a real e-mail into the inbox), the Azure job.
