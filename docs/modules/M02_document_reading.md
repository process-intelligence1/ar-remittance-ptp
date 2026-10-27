# M02 — Document reading and OCR

## What it does
Every stored e-mail body and attachment gets **clean text, tables and word positions** (so later
screens can highlight where a value was found), plus how it was read, the OCR confidence and the
language. Results are saved on the existing rows:

| Where | Columns |
|---|---|
| `ar.email_attachment` | `text_content`, `layout` (pages, words with boxes, tables), `parse_method`, `parse_status`, `parse_error`, `ocr_confidence`, `language`, `page_count`, `parse_reused`, `parse_ms`, `parsed_at` |
| `ar.email_message` | `body_layout` (tables found in the body), `language`, `status` → `PARSED` (or `FAILED`) |

## How it works
```
 attachment ──► router (by content + file name)
                 ├─ PDF ── text layer (PyMuPDF words + pdfplumber tables)
                 │         └─ page scanned or text layer unreadable ─► render 300 dpi ─► OCR   (mixed)
                 ├─ PNG / JPG / TIF (all pages) ─► OCR
                 ├─ DOCX ─ paragraphs + tables in order, headers, footers
                 ├─ XLSX ─ every sheet as a table, computed values, dates as ISO (2026-08-28)
                 ├─ CSV / TXT / HTML (≤ 2 MB)
                 └─ ZIP ── skipped ("container"): its files are separate rows since M01
 OCR = OpenCV (grey, scale to ~300 dpi, max 4000 px, deskew, light denoise)
       ─► Tesseract: orientation/script check, then eng+deu+fra+spa+por or jpn+eng (jpn_vert if weak);
          page mode 6 + preserve_interword_spaces=1; up to 3 readings for weak pages, best one kept;
          lines rebuilt top→bottom, left→right, wide gaps kept as two spaces (columns),
          Japanese characters joined without spaces
 body  ─► HTML <table>s, or column-aligned plain-text tables (R02, R13, R22 style)
```
- **Same file twice?** If a file with the same SHA-256 was parsed before, its result is copied
  (`parse_reused = true`, `parse_ms` = time the original took = time saved).
- **Timeout**: 120 s per document (each OCR call gets only the time that is left), then
  `FAILED` "timeout". One broken file never stops the others.
- **One document at a time**; large images are scaled down first (memory).
- **Language**: `langdetect` with a fixed seed, so results repeat.
- `layout` format: see the comment at the top of `backend/app/documents/__init__.py`
  (boxes are 0..1 of the page, so they work at any zoom).
- `OCR_ENGINE=azure_di` switches OCR to Azure Document Intelligence (F0). The code exists but is
  **off**, no Azure resource was created, and it has not been tested against a live service.

## How to try it
Laptop (in `D:\Finance\AR_Remittance\backend`, venv active):
```powershell
python -m scripts.parse_documents                     # stored e-mails not parsed yet
python -m scripts.parse_documents --email EML-000037  # one e-mail
python -m scripts.parse_documents --reparse           # everything again
python -m scripts.parse_documents --samples-report    # all 234 samples -> docs/reports/M02_samples_report.md
python -m pytest                                      # 314 tests
```
Azure (key in a variable in your own terminal — never shown):
```powershell
$u = Read-Host "API URL (see GitHub environment "demo" / Azure portal)"
$k = az keyvault secret show --vault-name kv-ardemo-snjjnahqgx3b4 --name admin-api-key --query value -o tsv
Invoke-RestMethod -Method Post "$u/api/admin/emails/EML-000002/parse" -Headers @{ "X-Admin-Key" = $k }
Invoke-RestMethod "$u/api/emails?limit=5"     # parse status, method, chars, OCR confidence per attachment
Remove-Variable k
```

## Results (27 Oct 2026, laptop)
- **All 234 samples parse, 0 failures**: 234 bodies + 188 attachments in 119 s.
  PDF 117 (107 text layer, 10 OCR, avg OCR confidence 89.7 %), images 29 (OCR, 89.5 %),
  DOCX 22, XLSX 18, CSV 1, ZIP 1 skipped (its PDF is its own row). 6 identical files reused (10.3 s saved).
- **51 body-only e-mails**; 24 bodies contain a table.
- Spot-check (5 scans, 2 Japanese): invoice numbers and amounts stay on the same line, e.g.
  `91005801  5.396,77  107,94  5.288,83` (German scan, 94 %), `JP-26-002884  2026 年 10 月 15 日
  306,900` (Japanese JPG, 88 %). Weakest: R03-0037 (72 %, stamps/noise around the table — numbers
  still readable), R19-0115 TIF (80 %, one line garbled).
- Stored laptop e-mails: 21 parsed, 1 file reused (5.3 s saved), 5 skipped (HTML > 2 MB, ZIP), 0 failed.

## Limitations
- OCR on the small Azure API container (¼ CPU, ½ GB) is only for 1–2 test files; the full volume
  runs in the M06 worker job.
- Column split of OCR tables is approximate (rows are reliable, columns can merge — e.g. a date
  and amount in one cell). M04 extraction works on rows.
- Noisy scans can contain stray characters (`|`, `:`, `'`) next to values; M04 normalises them.
- HTML attachments over 2 MB, password-protected PDFs and unknown types are `SKIPPED` with a note.
- PDFs: at most 50 pages are read (noted when more exist).
- `azure_di` engine untested (no resource).
- PyMuPDF is pinned to **1.28.2** on purpose: 2.0 pulls in an unused AI layout add-on
  (onnxruntime, networkx, models, ~80 MB). Results on all 234 samples are identical with 1.28.2.
