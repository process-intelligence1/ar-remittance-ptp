# API cold start (Option A: no always-on window, zero cost)

The API container scales to zero when idle. The first request after a quiet period has to start a replica. Observed before
this work (29 Oct 2026, full 240 MB image, migrations at start): **31 s** once, **about 90 s** another time.

## What was changed
1. **Two images from one Dockerfile.** `ar-api` (target `api`) is slim: no Tesseract, OpenCV, numpy, Pillow, pdfplumber,
   python-docx, openpyxl, pytesseract. It keeps PyMuPDF (PDF page images for the viewer). `ar-worker` (target `worker`) is the
   full image for the scheduled worker job. `requirements-api.txt` lists the slim set.
   - The per-stage admin endpoints (`/api/admin/emails/{ref}/parse|classify|extract|match`) need the OCR libraries; in the
     slim API they answer 501 "runs in the worker" (use `process-now` or `python -m scripts.process`).
2. **Migrations out of start-up.** Job `ar-migrate` (manual trigger, 0.25 vCPU / 0.5 GiB, same identity and database secret,
   runs `alembic upgrade head` from the slim image) runs once per deploy **inside Azure**; the deploy workflow starts it and
   waits before the new API goes live. The database firewall is not opened to GitHub. A failed migration stops the roll-out.
3. **Image tag is a Bicep parameter** (`imageTag` = commit SHA, no `:latest`) for `ar-api`, `ar-worker` and `ar-migrate`.
   `infra/deploy.ps1` passes the tag the API runs now, so a template deploy never changes the code version (`-ImageTag` overrides).
4. **Lazy imports + compiled code.** Gmail / Google libraries load only when the admin poll endpoint is used (the business-date
   helper moved to the light module `app/businessdate.py`); a test guards that `import app.main` pulls in none of the heavy
   libraries. Our own code is pre-compiled (`compileall`, hash-based .pyc) in the image; libraries already were.
5. **Login text:** "Starting the server... this can take up to 1 minute after a quiet period"; after 1 minute "Still starting -
   please wait or click Retry" with a Retry button.

## Roll-out order (one time; later deploys are done by the workflow)
1. Push -> the workflow builds both images and prints their compressed sizes (job summary). Do not approve its deploy yet.
2. `.\infra\deploy.ps1 -WhatIf -NoClientIp -ImageTag <sha>` then without `-WhatIf`: creates `ar-migrate`, switches the API to the
   slim image and the worker job to `ar-worker:<sha>`.
3. Start `ar-migrate` once by hand (the API no longer migrates at start); then approve the workflow deploy, which now runs the
   same sequence (migrate -> API -> worker) and the smoke test.

## Measurement
Method: no request for more than 15 minutes (replicas = 0), then one `curl` to `/api/health`; timeline from Azure's start events.

| | Cold start (first `/api/health` after 15+ min idle, zero replicas) |
|---|---|
| Before (observed 29 Oct) | 31 s and about 90 s |
| After, run 1 (3 Nov, 07:38 UTC) | **21.4 s** |
| After, run 2 (3 Nov, 07:57 UTC) | **24.9 s** |

Both are well under the 45 s limit, so the login text stays "up to 1 minute after a quiet period".

Image sizes (compressed): before 240 MB (one image); after **95 MB** (`ar-api`, slim) and **241 MB** (`ar-worker`, full).

Azure start events of run 1 (UTC, the request arrived at 07:38:29):
| Time | Event | Since request |
|---|---|---|
| 07:38:29 | scaled from 0 to 1 replica | 0 s |
| 07:38:30 | replica assigned to a node | 1 s |
| 07:38:32 - 07:38:40 | image pulled (99.6 MB, 8.2 s) | 11 s |
| 07:38:40 - 07:38:46 | container created (platform work, reads Key Vault secrets) | 17 s |
| 07:38:47 | container started; first start-up probe fails once (Python still importing) | 18 s |
| about 07:38:50 | health answers | 21.4 s |

Reading: the image pull (8 s) and the platform's container creation (6 s) are about two thirds of the wait and are not our code;
the app itself needs about 3 s from start to the first answer (lazy imports, compiled code, no migration at start-up).
Not tried (not needed, and each would need an owner decision): more CPU for the API, or an always-on window.
