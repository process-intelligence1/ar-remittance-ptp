# M04 — Extraction and normalisation

## What it does
For every remittance or promise-to-pay e-mail (M03 decides which), M04 reads a **header** and
**one line per invoice** (or per instalment) from the clean body and every attachment, and keeps
**where each value was found** (body or which file, page, position) for highlighting later.
Nothing is converted between currencies and nothing is matched yet — that is M05.

| Where | What |
|---|---|
| `ar.extraction` (one row per run, older runs kept with `is_current = false`) | payer name, sender domain, **customer number** (as quoted), **payer account / IBAN** (check digits verified), **our / your reference**, payment reference, advice number, **REM-… references**, payment date, promise date + wording, total, payment currency, **FX rate** (as stated), lines count, sum of lines, **total − sum of lines**, warnings, evidence |
| `ar.extraction_line` | line type (REMITTANCE / PTP), invoice number **as written** + **normalised**, amount (net; credits negative), **gross, deduction + reason** (TDS, bank charges…), **invoice currency** (only when the document states it) and **payment currency**, FX rate, credit-note flag, invoice date, promise date + **original wording**, instalment number, how it was found (table / text line / prose / mention / instalment), source kind and file, evidence |
| `ar.email_message.status` | `CLASSIFIED` → `EXTRACTED`; audit entry `EMAIL_EXTRACTED` |
| `ar.rule_config` key `extraction` | tolerance for "amount matches" (2 %), total check (0.01), US date hint, optional LLM switch (`none`) |

## How it works
```
 body_text_clean (quoted reply history removed) + parsed attachments (text, tables, word boxes)
   │
   ├─ lines (app/extraction/lines.py)
   │    tables: column headers recognised in EN/DE/FR/ES/PT/JA, OCR typos tolerated ("Involce", "Amount pald")
   │    column-aligned text (text PDFs, OCR): header line, then each value goes to the column it sits under
   │    prose: "JP-26-002358 (AUD 951.50)", "Payment of KWD 138.000 for MUM/2627/05088 ...", lists of invoices
   │    SWIFT field 70: /INV/UK-1043976/1338.08 (also wrapped over two lines)
   │    instalments: "- 28 Oct 2026: GBP 4,176.00" lines under a promise -> one line per instalment
   ├─ header (header.py): labelled values ("Payment reference:", "Ihre Kunden-Nr.", "Votre n° client",
   │    "Ordering customer", "Debit account", "Value date", "日付", ...) and prose ("we transferred US$9,757.59",
   │    "heute ueberwiesen" = the e-mail date); an advice's own date is the payment-date fallback
   └─ merge (extractor.py): the same invoice found in several places = one line (table > aligned text
        > prose > mention; the others become evidence); M03 flags decide the line type, in a mixed e-mail
        a line is PTP when its number sits in a promise sentence; total vs sum of lines is checked
```
Building blocks (all unit-tested):
- **Invoice numbers** (`refs.py`): shapes taken from BSID (8 digits 90/91…, `MUM/2627/04212`, `UK-1043617`,
  `JP-26-002330`, `FA2026-09168`, `SRV-100354`, `SI12600424`, `CN-…`; 10-digit numbers only inside an
  invoice column). Prefixes such as `Inv#`, `INV-` are dropped. **`normalise_ref()` is the one rule for both
  sides of matching**: upper case; spaces and `- / .` removed; leading zeros removed. In an invoice-number
  column a number is taken as written even if it fits no shape (`MUM/2627/0500`) — M05 then says NONE.
- **Amounts** (`amounts.py`): `15.999,58` `11 353,25` `3'797.48` `₹3,56,639.73` `Rs. 32,11,468.71`
  `¥2,079,824` `1,402,390円` `KWD 138.000` (3 decimals from `sap.tcurx`) `US$` `S$` `R$` `€` `£` `₩`; negatives
  `-1,234.00` `1,234.00-` `(1,234.00)` `1,234.00 CR`.
- **Dates** (`dates.py`, own parser — no extra library): ISO, `28.10.2026`, `28/10/2026` (US month-first for
  US-looking senders; ambiguous ones flagged), `16-Nov-2026`, `18 Nov 2026`, `Nov 18, 2026`, `23. Oktober 2026`,
  `25 octobre 2026`, `27 de noviembre de 2026`, `2026年11月27日`, `令和8年11月27日`, `11月25日`; relative promise
  dates resolved against the e-mail date with the wording kept: *next Friday, end of (next) month, within 7
  days, in 10 days, tomorrow, next week* + DE/FR/ES/PT/JA (*Ende des Monats, fin de mois, dentro de 5 dias,
  próxima sexta-feira, 月末, 来週, 7日以内*…).

**Fixes to earlier modules found on the way:** (1) M01's reply-history cleaner cut an instalment list
("- 28 Oct 2026: GBP 4,176.00" looked like "On … wrote:" to it) — it now only cuts when the removed part
really is quoted history; `python -m scripts.extract --reclean` re-cleans stored bodies. (2) M03's text
folding collapsed runs of spaces, which hid "Label      value" columns — it can now keep them.

## Results (honest)
Report: [`docs/reports/M04_extraction_report.md`](../reports/M04_extraction_report.md)
(`python -m scripts.evaluate --stage extraction`). There are no hand-made answers, so **BSID is the judge**:
a line is a hit when its number exists in BSID and its amount is within 2 % (or its gross is, when a
deduction was taken). **Held-out** = every 3rd sample of each scenario, never studied while writing the rules.

| Referenced remittance lines | Lines | Number in BSID | **Strict hit** | Hit or deliberate part-payment |
|---|---|---|---|---|
| Dev | 300 | 95.7 % | 79.7 % | 92.7 % |
| **Held-out** | 111 | 95.5 % | **80.2 %** | 91.9 % |
| Dev, without the 5 scenarios where no line can match | 280 | 99.3 % | 85.4 % | 97.5 % |
| **Held-out**, same | 105 | 98.1 % | **84.8 %** | 96.2 % |

- **Held-out ≈ dev**: the rules generalise to samples they were not written on.
- The strict number misses the **85 % target**. The misses are mostly *deliberate* in the samples:
  part-payments and instalments (R03, R07, R27…), and 5 scenarios where not one line can match BSID —
  R02 (amount column empty), R04 / R16 (invoice numbers that do not exist), R06 (paid in another currency),
  R26 (part-payments + an OCR misread). Those are exceptions for M05 to send to review, not reading errors.
- **Amounts read correctly by the document's own numbers** (lines add up exactly to the stated total):
  dev 88.3 % (113/128), held-out 95.9 % (47/49). Only 2 e-mails have a total ≠ sum of lines — both OCR
  misreads in scans (R21-0123, R26-0149).
- **Promises:** 60 PTP lines, promise date found for all 60, P08 instalment plans split into 8 instalment lines.
- **E-mails without lines:** 12 — all R12 / R13 / R28 (no invoice numbers by design; M05 finds them by amount).
- **Per source:** Text PDF 97 % / OCR 91 % / Word 93 % / Excel 100 % / body 100 % of numbers found in BSID.
- **Laptop database (21 real e-mails):** 18 extracted (all with lines, totals and references), 3 out of scope skipped.
- Not in the samples, proven by unit tests only: exchange rates, REM- references, relative promise dates,
  credit-note formats.

## How to try it
From the `backend` folder:
```
python -m scripts.extract                      # classified e-mails not extracted yet
python -m scripts.extract --email EML-000037   # one e-mail (again)
python -m scripts.extract --reextract          # all again (history kept)
python -m scripts.extract --reclean            # re-clean stored bodies (reply-history fix), then extract
python -m scripts.evaluate --stage extraction  # the report
```
API: `GET /api/emails` shows each e-mail's extraction status and line count (no numbers or amounts before
the login exists). `POST /api/admin/emails/{ref}/extract` (header `X-Admin-Key`) extracts one stored e-mail;
it must be classified first, otherwise 409.

## Limitations
- OCR misreads stay misreads (`5947.10` for `€947.10`, `5162600347` for `SI62600347`); M05's NEAR match and
  the amount comparison with BSID catch most of them and send them to review.
- The invoice currency is only filled in when the document states it; otherwise M05 uses BSID's.
- Payer names come from letterheads / signatures; customer identification itself is M05 (ADR6, KNA1, IBAN).
- Optional hosted-LLM fallback: interface only (`llm_provider = none`), nothing is ever sent.
- Extraction runs from the script or the admin endpoint; automatic processing comes with the M06 worker.
