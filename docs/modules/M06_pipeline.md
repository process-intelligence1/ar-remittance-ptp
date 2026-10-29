# M06 - Pipeline and worker

## What it does
E-mails now move through the whole chain by themselves:
**read (M02) -> classify (M03) -> extract (M04) -> match (M05)**. Nobody has to run a script.

## How it works
- `app/pipeline.py` - `process_email()` looks at what is already stored for an e-mail and runs only the
  missing stages, so a retry carries on at the stage that failed. Every finished or failed stage writes an
  `ar.audit_log` entry (`PIPELINE_STAGE_DONE` / `PIPELINE_STAGE_FAILED`, actor "system"). A failure puts the
  e-mail in status FAILED with `error = "<STAGE>: <reason>"`.
- `app/jobs.py` - the queue in table `ar.job`. One active `PROCESS_EMAIL` job per e-mail. A failed job waits
  1 minute, then 5 minutes, and after the 3rd failed attempt stays FAILED (error text on the job and the
  e-mail). Workers claim jobs with `FOR UPDATE SKIP LOCKED`, so two workers never take the same one. A job left
  RUNNING by a crashed worker is released after 15 minutes.
- `app/worker.py` - one round: poll Gmail (only where `POLLER_ENABLED=true`), queue every unfinished e-mail,
  work through the jobs (stops starting new e-mails after 180 s), PTP checks (empty until M10).
  `python -m app.worker --once` (Azure job) or `--loop --interval 60` (laptop).
- `app/azure_jobs.py` + `POST /api/admin/process-now` (needs `X-Admin-Key`) - starts the Azure worker job
  **immediately** through the Azure management API, using the API's managed identity. Optional
  `?requeue_failed=true` first gives FAILED jobs a fresh set of attempts. `GET /api/admin/jobs` lists jobs and errors.
- Laptop: `python -m scripts.process` (all unfinished), `--email EML-...` (one, errors shown), `--jobs`.

## Azure (infra/main.bicep)
- Container Apps **Job** `ar-worker`: same image, command `python -m app.worker --once`, cron `*/10 * * * *`
  (parameter `workerCron`; was every 5 minutes at first), 0.5 vCPU / 1 GiB, 1 run at a time, no job-level retry.
- Custom role **AR Worker Job Starter**: one permission, `Microsoft.App/jobs/start/action`. Defined in the
  resource group, **assigned only on the job resource** to the API's identity `id-ar-api`. It can start this
  job and nothing else (cannot read, change or start anything else).
- Policy "allowed resource types" gains `Microsoft.App/jobs` and `Microsoft.Authorization/roleDefinitions`.
- The deploy workflow now updates the job's image together with the API, and the clean-up keeps the job's image.

## Free-grant maths (Container Apps: 180,000 vCPU-s and 360,000 GiB-s per month, shared with the API)
Measured in Azure on 29 Oct 2026 (job 0.5 vCPU / 1 GiB):

| Run | Duration |
|---|---|
| Idle (nothing to process) | 37 s and 39 s (the second was started with "Process now") |
| Busy: 1 new e-mail (R19-0116: read, OCR, classify, extract, match) | 66 s |
| Busy: backlog of 12 older e-mails incl. OCR | 134 s (about 10 s per e-mail) |

Most of an idle run is starting Python and loading the libraries, not work.
- Every 5 minutes = 8,640 runs/month x 38 s x 0.5 vCPU = ~164,000 vCPU-s (91 %) and ~328,000 GiB-s (91 %) - too
  close to the limit once busy runs and the API are added. **Rejected.**
- Every 10 minutes (chosen) = 4,320 runs x 38 s = ~82,000 vCPU-s (46 %) and ~164,000 GiB-s (46 %). Busy runs: even
  200 e-mails a month at ~10 s each add only ~1,000 vCPU-s. The API (0.25 vCPU, scale to zero) uses little.
- "Process now" starts a run at once, so presenters never wait for the schedule.
- Re-check after a few days with `az containerapp job execution list -g rg-ar-demo -n ar-worker`.

## Limits / decisions
- Unreadable attachment: the read stage fails and is retried. On the LAST attempt the pipeline carries on with the
  body and the readable attachments; every resulting row gets the review reason "Attachment unreadable" and is
  never auto-processed (an AUTO_PROCESS row becomes MANUAL_REVIEW / PENDING_REVIEW). `email.error` keeps
  `ATTACHMENT_UNREADABLE: ...` and the audit log has `ATTACHMENT_UNREADABLE_REVIEW`.
- Rows an analyst has already acted on are never re-matched (M05 rule); the pipeline treats this as "done".
- The Gmail poll stays guarded by the existing lock and `POLLER_ENABLED`.
- Host-neutral: `python -m app.worker --once` has no Azure code and needs only environment settings (database, Gmail,
  storage). Any scheduler can run it (cron, Task Scheduler, another cloud's job). The only Azure-specific code is the
  optional `app/azure_jobs.py` behind `POST /api/admin/process-now`; elsewhere that endpoint answers 409.
