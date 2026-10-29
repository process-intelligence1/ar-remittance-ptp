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
- Container Apps **Job** `ar-worker`: same image, command `python -m app.worker --once`, cron `*/5 * * * *`
  (parameter `workerCron`), 0.5 vCPU / 1 GiB, 1 run at a time, no job-level retry.
- Custom role **AR Worker Job Starter**: one permission, `Microsoft.App/jobs/start/action`. Defined in the
  resource group, **assigned only on the job resource** to the API's identity `id-ar-api`. It can start this
  job and nothing else (cannot read, change or start anything else).
- Policy "allowed resource types" gains `Microsoft.App/jobs` and `Microsoft.Authorization/roleDefinitions`.
- The deploy workflow now updates the job's image together with the API, and the clean-up keeps the job's image.

## Free-grant maths (Container Apps: 180,000 vCPU-s and 360,000 GiB-s per month, shared with the API)
- 5-minute schedule = about 8,640 runs a month. A run that finds nothing to do takes about 15-20 s.
- 8,640 x 20 s x 0.5 vCPU = ~86,000 vCPU-s (48 %); 8,640 x 20 s x 1 GiB = ~173,000 GiB-s (48 %).
- Runs that process e-mails (OCR) take longer. If the measured average goes above ~30 s, set `workerCron`
  to every 10 minutes. To be checked against real run times after the first Azure days.

## Limits / decisions
- An e-mail with one unreadable attachment fails the read stage, is retried 3 times, then stays FAILED and
  visible (it is not auto-processed from the body alone). Re-run with `process-now?requeue_failed=true`.
- Rows an analyst has already acted on are never re-matched (M05 rule); the pipeline treats this as "done".
- The Gmail poll stays guarded by the existing lock and `POLLER_ENABLED`.
