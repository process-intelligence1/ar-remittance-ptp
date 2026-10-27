# M05 — Customer identification, BSID matching, scoring, duplicates

## What it does
Every invoice line M04 extracted becomes **one `ar.work_item` row** (the rows of the future Action Queue):
which customer and company code, which open BSID item it matches and how (EXACT / NEAR / NONE on
XBLNR, BELNR or VBELN), the five score components, the confidence and where that number came from,
the decision, status, recommended action, assigned role and SLA due date — and, for a repeat, the row
it duplicates. Every BSID item considered is kept in `ar.match_candidate` ("why this match"), and
every promise becomes an `ar.ptp_commitment` row (one per instalment, status OPEN) for M10.

| Where | What |
|---|---|
| `ar.work_item` | `kunnr`, `bukrs`, `bsid_id`, `match_field`, `match_level`, `invoice_match_score`, amount / sender→company code / name / date scores, `raw_score`, **`formula_confidence`**, **`confidence_score`**, **`confidence_source`** (FAST_PATH / FORMULA), `fast_path_override`, `confidence_category`, `decision`, `status`, `review_reasons`, `exception_reason`, `duplicate_of_id`, `recommended_action`, `assigned_role`, `sla_due_at`, cluster flags, **`customer_match_method` / `_score` / `customer_evidence`**, link to the extraction line |
| `ar.match_candidate` | every candidate item with its scores; `chosen` = the one used |
| `ar.ptp_commitment` | promise date, amount, currency, instalment number |
| `ar.email_message.status` | `EXTRACTED` → `PROCESSED`; audit entry `WORK_ITEMS_CREATED` |

## How it works
```
 extraction (M04) ──► customer (customers.py), strongest signal first:
                        INVOICE (owner of exactly matched invoices) > SENDER_ADDRESS (ADR6) > CUSTOMER_NUMBER
                        (quoted = KUNNR) > IBAN (KNBK) > SENDER_DOMAIN (one customer) > NAME (difflib >= 0.85)
                        + KNVP payer relationships (a holding company may pay for its subsidiaries)
                  ──► per line: invoice match (invoice_match.py)
                        EXACT 1.00  same after normalise_ref() - XBLNR, or BELNR / VBELN (alternates: EXACT only)
                        NEAR  0.70  same length, ONE character differs and it is an OCR pair (0/O 1/I/L 5/S 8/B 2/Z)
                        NONE  0.00  -> EXCEPTION "No BSID match found"
                  ──► score (scoring.py, all values from ar.rule_config)
                        raw = invoice 0.35 + amount 0.30 + sender->company code 0.10 + name 0.05 + date 0.10
                        formula confidence = raw / 0.90
                        fast path (EXACT + open + same currency): amount within 2 % -> 92 %, amount missing -> 91 %
                        confidence = max(fast-path value, formula); confidence_source says which won
                        decision: >= 80 + BSID = Auto Process, 40-79 Manual Review, < 40 Manual Investigation;
                        review reasons turn Auto Process into Manual Review
                  ──► no invoice numbers (unreferenced.py): open invoices of the payer that add up to the paid
                        amount (within 0.5 %, up to 6 invoices, fewest first) -> always Manual Review
                  ──► duplicates (duplicates.py): same invoice + customer + amount (±0.01 %) + currency + sender
                        domain within 7 days, or an identical attachment (SHA-256); only rows of the same kind
                        (a payment after a promise is not a duplicate of the promise)
```
**Review reasons** (a high score still goes to an analyst): possible OCR misread (NEAR), payment block
(`ZLSPR = R`), several open items carry the number (e.g. the same number in two company codes), **invoice
of another customer than the sender** (third-party payment, unless related in KNVP), no invoice number
(found by amount), promise date missing. **Credit notes** (`SHKZG = H`) are matched as negative amounts.
**Roles:** remittances → CASH_APPLICATION, promises → COLLECTIONS_ANALYST, exceptions / duplicates /
investigations → AR_ANALYST. **SLA:** 2 business days for review, 1 for exceptions (rule `sla`).

### Confidence = max(fast path, formula) — the KB worked example recalculated
Invoice `23756669` vs BSID `23756668`, $13,497.36 vs $13,464.77 (0.24 %), name similarity 0.957, 144 days,
sender mapped. (The prototype's own "85.34 %" does not follow raw / 0.90: 0.893 / 0.90 = 99.2 %.)

| Variant | Invoice match | Raw | Formula | Final | Source | Decision |
|---|---|---|---|---|---|---|
| As written — 9 vs 8 is no OCR pair | NONE 0.00 | 0.508 | 56.4 % | 56.4 % | FORMULA | **Exception** "No BSID match found" |
| OCR misread (`2375666B`) | NEAR 0.70 | 0.753 | 83.7 % | 83.7 % | FORMULA | **Manual Review** (NEAR is always reviewed) |
| Exact number | EXACT 1.00 | 0.858 | 95.3 % | **95.3 %** = max(92, 95.3) | FORMULA | **Auto Process** |
| Exact, amount missing | EXACT 1.00 | 0.558 | 62.0 % | **91 %** = max(91, 62.0) | FAST_PATH | **Auto Process** |

All four are unit tests (`tests/test_matching.py`).

## Results (honest)
Report: [`docs/reports/M05_matching_report.md`](../reports/M05_matching_report.md)
(`python -m scripts.evaluate --stage matching` — all 234 samples in date order, in memory).

| Set | Rows | Auto Process | Manual Review | Exception | Duplicate | Out of scope |
|---|---|---|---|---|---|---|
| Dev | 367 | 65.4 % | 22.3 % | 3.8 % | 4.6 % | 3.8 % |
| **Held-out** | 137 | 61.3 % | 22.6 % | 3.6 % | 10.2 % | 2.2 % |

- Every review / exception has a stated reason, and they line up with the scenarios: R04 / R16 unknown
  invoice numbers → Exception; R06 / P07 invoices of another customer → Review; R12 / R13 / R28 found by
  amount → Review; R17 same number in two company codes → Review; R18 payment block → Review; R24
  re-sent advices → all 28 rows Duplicate; R25 corrected advices → 3 Duplicates; part-payments → Review.
- **Confidence source:** the fast path applied to 361 rows; the stored value came from the formula for
  283 of them (formula higher) and from the fast path for 78.
- **Customer identification:** identified for 215 of 217 in-scope e-mails (99.1 %); agrees with the ADR6
  sender in 97.6 %, with the quoted customer number in 98.8 %, with the owner of exactly matched invoices
  in 99.5 %. The 5 sender disagreements are the 6 third-party payments, all sent to review; the 2 not
  identified are R19 e-mails from unknown domains (group domain / Gmail).
- **JP-26-002271 (P03-0193)** → customer 102419, SGD 8,300.00, EXACT, 92 % (FAST_PATH; formula 91.1 %),
  Auto Process; the promise (27 Nov 2026) is saved as a PTP commitment.
- **Re-sent sample** → DUPLICATE pointing to the original (`test_resent_sample_becomes_duplicate`; also in
  the laptop database: EML-000018 / EML-000037, the same R01-0007 advice).
- **Laptop database (21 real e-mails):** 16 Auto Process, 2 Manual Review (a real OCR misread `S112600517`
  caught as NEAR, and a part-payment), 1 Duplicate, 3 Out of scope.

## How to try it
From the `backend` folder:
```
python -m scripts.match                      # extracted e-mails not matched yet
python -m scripts.match --email EML-000037   # one e-mail (again)
python -m scripts.match --rematch            # all again (rows an analyst has acted on are never replaced)
python -m scripts.evaluate --stage matching  # the report
```
API: `GET /api/emails` shows the number of work items per decision. `POST /api/admin/emails/{ref}/match`
(header `X-Admin-Key`) matches one extracted e-mail (409 if not extracted yet); it returns entry ids,
match levels, confidence, its source and the decisions — no amounts or invoice numbers before the login.

## Limitations
- Re-matching replaces only untouched rows; duplicates pointing at replaced rows are re-pointed.
- Customer names use difflib (no extra library); revisit only if the report shows customers missed by name
  (none so far — the NAME method was never needed on the samples).
- Payer / currency cluster flags stay blank until a customer has 3 past rows from the same sender domain.
- Amounts in another currency than BSID score 0 for amount; nothing is converted (TCURR comes with M07 KPIs).
- Matching runs from the script or the admin endpoint; automatic processing comes with the M06 worker.
