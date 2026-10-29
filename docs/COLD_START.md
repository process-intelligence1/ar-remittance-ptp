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

| | Cold start |
|---|---|
| Before (observed) | 31 s and about 90 s |
| After, run 1 | _to be measured_ |
| After, run 2 | _to be measured_ |

Image sizes (compressed): before 240 MB (one image) - after: _to be measured_ (api / worker).
