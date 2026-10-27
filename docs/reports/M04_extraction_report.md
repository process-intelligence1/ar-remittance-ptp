# M04 — extraction report

217 in-scope sample e-mails (61 held out), 471 invoice lines extracted. Judged against BSID (4,840 open items): there are no hand-made answers, so a line counts as a **hit** when its invoice number exists in BSID (XBLNR, or exactly BELNR / VBELN) and its amount is within 2 % of the BSID amount (or its gross amount is, when a deduction was taken). Run time 13 s.

**Dev** = the two thirds of the samples the rules were written on. **Held-out** = every 3rd sample of each scenario, never looked at while writing the rules - the honest number.

## Headline (referenced remittance lines; R12, R13, R28 have no invoice numbers by design)

| Set | Lines | Number in BSID | Strict hit (number + amount within 2 %) | Hit or deliberate part-payment |
|---|---|---|---|---|
| Dev | 300 | 95.7 % | **79.7 %** | 92.7 % |
| **Held-out** | 111 | 95.5 % | **80.2 %** | 91.9 % |
| All | 411 | 95.6 % | **79.8 %** | 92.5 % |
| Dev without R02, R04, R06, R16, R26 | 280 | 99.3 % | **85.4 %** | 97.5 % |
| **Held-out** without R02, R04, R06, R16, R26 | 105 | 98.1 % | **84.8 %** | 96.2 % |

The last rows leave out the scenarios in which **not a single line** matches BSID (R02, R04, R06, R16, R26): they are built as exceptions (amount column empty, invoice numbers that do not exist, payment in another currency, ...), which M05 must send to review - not reading errors. The strict number above is the one BUILD_PLAN asks for; most of its misses are deliberate part-payments (see PARTIAL per scenario).

**Read correctly by the document's own numbers** (remittance e-mails whose lines add up exactly to the stated total): dev 88.3 % (113/128), held-out 95.9 % (47/49). The others state no total, or a line was missed / misread (both listed below).

Line categories: EXACT = amount within 2 % of BSID; GROSS = gross within 2 % (deduction taken); PARTIAL = less than the open amount (short payment / instalment - deliberate in many samples); OTHER_AMOUNT = more than BSID, another currency, or misread; NO_AMOUNT = number only (e.g. a promise without a per-invoice amount); NOT_IN_BSID = no such invoice number (unknown invoice or OCR misread - M05 decides NEAR / NONE).

## Per scenario (all lines)

| Scenario | E-mails | Lines | EXACT | GROSS | PARTIAL | OTHER_AMOUNT | NO_AMOUNT | NOT_IN_BSID | Hit | No lines |
|---|---|---|---|---|---|---|---|---|---|---|
| P01 | 9 | 9 | 9 | 0 | 0 | 0 | 0 | 0 | 100.0 % | 0 |
| P02 | 6 | 17 | 13 | 0 | 2 | 0 | 2 | 0 | 76.5 % | 0 |
| P03 | 4 | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 100.0 % | 0 |
| P03R | 4 | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 100.0 % | 0 |
| P05 | 3 | 8 | 7 | 0 | 1 | 0 | 0 | 0 | 87.5 % | 0 |
| P05R | 3 | 6 | 5 | 0 | 1 | 0 | 0 | 0 | 83.3 % | 0 |
| P06 | 5 | 17 | 7 | 0 | 0 | 0 | 10 | 0 | 41.2 % | 0 |
| P07 | 3 | 3 | 0 | 0 | 1 | 0 | 0 | 2 | 0.0 % | 0 |
| P08 | 3 | 8 | 0 | 3 | 5 | 0 | 0 | 0 | 37.5 % | 0 |
| R01 | 18 | 18 | 15 | 0 | 2 | 0 | 0 | 1 | 83.3 % | 0 |
| R02 | 5 | 5 | 0 | 0 | 1 | 0 | 4 | 0 | 0.0 % | 0 |
| R03 | 14 | 154 | 126 | 0 | 23 | 2 | 2 | 1 | 81.8 % | 0 |
| R04 | 8 | 8 | 0 | 0 | 0 | 0 | 0 | 8 | 0.0 % | 0 |
| R05 | 7 | 11 | 10 | 0 | 1 | 0 | 0 | 0 | 90.9 % | 0 |
| R06 | 4 | 4 | 0 | 0 | 2 | 2 | 0 | 0 | 0.0 % | 0 |
| R07 | 7 | 7 | 0 | 1 | 6 | 0 | 0 | 0 | 14.3 % | 0 |
| R08 | 6 | 6 | 3 | 3 | 0 | 0 | 0 | 0 | 100.0 % | 0 |
| R09 | 6 | 13 | 7 | 4 | 2 | 0 | 0 | 0 | 84.6 % | 0 |
| R10 | 6 | 21 | 21 | 0 | 0 | 0 | 0 | 0 | 100.0 % | 0 |
| R11 | 4 | 4 | 0 | 2 | 0 | 2 | 0 | 0 | 50.0 % | 0 |
| R12 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | - | 5 |
| R13 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | - | 4 |
| R14 | 4 | 4 | 0 | 3 | 1 | 0 | 0 | 0 | 75.0 % | 0 |
| R16 | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 5 | 0.0 % | 0 |
| R17 | 4 | 4 | 4 | 0 | 0 | 0 | 0 | 0 | 100.0 % | 0 |
| R18 | 4 | 4 | 4 | 0 | 0 | 0 | 0 | 0 | 100.0 % | 0 |
| R19 | 5 | 7 | 5 | 0 | 1 | 0 | 0 | 1 | 71.4 % | 0 |
| R20 | 4 | 9 | 9 | 0 | 0 | 0 | 0 | 0 | 100.0 % | 0 |
| R21 | 7 | 15 | 11 | 0 | 2 | 1 | 0 | 1 | 73.3 % | 0 |
| R22 | 6 | 13 | 13 | 0 | 0 | 0 | 0 | 0 | 100.0 % | 0 |
| R23 | 3 | 7 | 6 | 0 | 1 | 0 | 0 | 0 | 85.7 % | 0 |
| R24 | 6 | 28 | 24 | 2 | 2 | 0 | 0 | 0 | 92.9 % | 0 |
| R25 | 6 | 12 | 9 | 2 | 1 | 0 | 0 | 0 | 91.7 % | 0 |
| R26 | 4 | 4 | 0 | 0 | 3 | 0 | 0 | 1 | 0.0 % | 0 |
| R27 | 4 | 4 | 0 | 2 | 2 | 0 | 0 | 0 | 50.0 % | 0 |
| R28 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | - | 3 |
| R29 | 5 | 10 | 6 | 4 | 0 | 0 | 0 | 0 | 100.0 % | 0 |
| R30 | 3 | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 100.0 % | 0 |
| R31 | 5 | 5 | 4 | 0 | 1 | 0 | 0 | 0 | 80.0 % | 0 |
| R32 | 5 | 6 | 6 | 0 | 0 | 0 | 0 | 0 | 100.0 % | 0 |

## Hit-rate per source (where the line's values came from; referenced remittance lines)

| Source | Lines | Number in BSID | Strict hit | Hit or part-payment |
|---|---|---|---|---|
| Body | 35 | 100.0 % | 74.3 % | 85.7 % |
| Text PDF | 213 | 97.2 % | 79.8 % | 96.2 % |
| OCR (scan / image) | 101 | 91.1 % | 78.2 % | 86.1 % |
| Excel | 21 | 100.0 % | 95.2 % | 95.2 % |
| Word | 40 | 92.5 % | 82.5 % | 92.5 % |
| CSV | 1 | 100.0 % | 0.0 % | 100.0 % |

## Promises (PTP lines)

60 PTP lines; promise date found for 60; instalment lines 8; number in BSID 96.7 %.

## E-mails with no lines found (12)

- R12-0086 (dev) - no invoice numbers by design
- R12-0087 (dev) - no invoice numbers by design
- R12-0088 (heldout) - no invoice numbers by design
- R12-0089 (dev) - no invoice numbers by design
- R12-0090 (dev) - no invoice numbers by design
- R13-0091 (dev) - no invoice numbers by design
- R13-0092 (dev) - no invoice numbers by design
- R13-0093 (heldout) - no invoice numbers by design
- R13-0094 (dev) - no invoice numbers by design
- R28-0157 (dev) - no invoice numbers by design
- R28-0158 (dev) - no invoice numbers by design
- R28-0159 (heldout) - no invoice numbers by design

## Total vs sum of lines - mismatches (2)

| Sample | Set | Total | Sum of lines | Difference |
|---|---|---|---|---|
| R21-0123 | heldout | 7779653.60 INR | 88604782.16 | -80825128.56 |
| R26-0149 | dev | 11819.48  | 7331181948 | -7331170128.52 |

Remittance e-mails with lines but no stated total (cannot be checked): 10 - R02-0019, R02-0020, R02-0021, R02-0022, R02-0023, R03-0025, R05-0046, R07-0058, R08-0067, R24-0141

## Lines to look at (27: number not in BSID, or amount above BSID / other currency)

| Sample | Set | Number as read | Amount | Currency | Category | BSID | Source | Method |
|---|---|---|---|---|---|---|---|---|
| P07-0213 | dev | 90039164 | 1930.94 | USD | NOT_IN_BSID | - | Text PDF | table |
| P07-0214 | heldout | 90039201 | 10117.39 | USD | NOT_IN_BSID | - | Text PDF | table |
| R01-0009 | heldout | S112600517 | 12941.38 | USD | NOT_IN_BSID | - | OCR (scan / image) | table |
| R03-0034 | dev | 91004752 | 5947.10 | EUR | OTHER_AMOUNT | 947.100 EUR; 947.100 EUR | OCR (scan / image) | table |
| R03-0034 | dev | 91004753 | 5949.68 | EUR | OTHER_AMOUNT | 949.680 EUR; 949.680 EUR | OCR (scan / image) | table |
| R03-0037 | dev | 122600314 | 3273.00 | EUR | NOT_IN_BSID | - | OCR (scan / image) | table |
| R04-0038 | dev | MUM/2627/0500 | 1720934.03 | INR | NOT_IN_BSID | - | Text PDF | table |
| R04-0039 | dev | FA2026-08885 | 2800.80 | EUR | NOT_IN_BSID | - | Word | table |
| R04-0040 | heldout | 9003155 | 8234.77 | USD | NOT_IN_BSID | - | Text PDF | table |
| R04-0041 | dev | 91004868 | 2507.33 | EUR | NOT_IN_BSID | - | Text PDF | table |
| R04-0042 | dev | UK-1044387 | 6162.00 | GBP | NOT_IN_BSID | - | Text PDF | table |
| R04-0043 | heldout | UK-103419 | 38008.79 | GBP | NOT_IN_BSID | - | OCR (scan / image) | table |
| R04-0044 | dev | MUM/2627/0422 | None | INR | NOT_IN_BSID | - | OCR (scan / image) | table |
| R04-0045 | dev | 9100551 | 16411.31 | EUR | NOT_IN_BSID | - | Text PDF | table |
| R06-0053 | dev | 91005417 | 21607.00 | SEK | OTHER_AMOUNT | 2353.030 EUR; 2353.030 EUR | Text PDF | table |
| R06-0055 | heldout | 90032587 | 19353.68 | USD | OTHER_AMOUNT | 4600.000 USD; 4600.000 USD | Body | table |
| R11-0084 | heldout | SRV-100610 | 3086.50 | USD | OTHER_AMOUNT | 2805.910 USD | Text PDF | table |
| R11-0085 | dev | 91005646 | 4554.9 | CHF | OTHER_AMOUNT | 4338.000 CHF; 4338.000 CHF | Excel | table |
| R16-0099 | dev | FA2026-09909 | 431.31 | EUR | NOT_IN_BSID | - | Word | table |
| R16-0100 | dev | UK-1048799 | None | GBP | NOT_IN_BSID | - | OCR (scan / image) | table |
| R16-0101 | heldout | JP-26-001724 | 1456.68 | SGD | NOT_IN_BSID | - | OCR (scan / image) | table |
| R16-0102 | dev | MUM/2627/01606 | 3554.07 | USD | NOT_IN_BSID | - | Word | table |
| R16-0103 | dev | 91012283 | 229.92 | EUR | NOT_IN_BSID | - | Text PDF | table |
| R19-0115 | dev | 5162600347 | 11990.05 | EUR | NOT_IN_BSID | - | OCR (scan / image) | table |
| R21-0123 | heldout | SRV-300475 | 375369.77 | INR | NOT_IN_BSID | - | OCR (scan / image) | table |
| R21-0123 | heldout | MUM/2627/04531 | 81641544 | INR | OTHER_AMOUNT | 1360615.440 INR | OCR (scan / image) | table |
| R26-0149 | dev | MUNI2627/04977 | 7331181948 |  | NOT_IN_BSID | - | OCR (scan / image) | table |
