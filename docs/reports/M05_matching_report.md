# M05 — matching report

234 sample e-mails processed in date order (classification -> extraction -> matching, nothing saved), 504 work items. Duplicates are checked against the earlier samples. Run time 15 s.

Confidence = max(fast-path value, formula); the fast path decides the category / decision. **Held-out** = every 3rd sample per scenario (never studied while writing M04's rules).

## Decision distribution

| Set | Rows | AUTO_PROCESS | MANUAL_REVIEW | MANUAL_INVESTIGATION | EXCEPTION | DUPLICATE | OUT_OF_SCOPE |
|---|---|---|---|---|---|---|---|
| Dev | 367 | 240 (65.4 %) | 82 (22.3 %) | 0 (0.0 %) | 14 (3.8 %) | 17 (4.6 %) | 14 (3.8 %) |
| **Held-out** | 137 | 84 (61.3 %) | 31 (22.6 %) | 0 (0.0 %) | 5 (3.6 %) | 14 (10.2 %) | 3 (2.2 %) |
| All | 504 | 324 (64.3 %) | 113 (22.4 %) | 0 (0.0 %) | 19 (3.8 %) | 31 (6.2 %) | 17 (3.4 %) |

Confidence source: fast path applied to 361 rows - the stored value came from the FAST_PATH for 78 and from the higher FORMULA for 283; 126 rows had no fast path (formula).

## Decision distribution per scenario

| Scenario | E-mails | Rows | AUTO_PROCESS | MANUAL_REVIEW | MANUAL_INVESTIGATION | EXCEPTION | DUPLICATE | OUT_OF_SCOPE | Main review / exception reasons |
|---|---|---|---|---|---|---|---|---|---|
| O01 | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 3 |  |
| O02 | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 3 |  |
| O03 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 2 |  |
| O04 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 2 |  |
| O05 | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 3 |  |
| O06 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 2 |  |
| O07 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 2 |  |
| P01 | 9 | 9 | 9 | 0 | 0 | 0 | 0 | 0 |  |
| P02 | 6 | 17 | 15 | 2 | 0 | 0 | 0 | 0 | amount differs from BSID (2) |
| P03 | 4 | 5 | 5 | 0 | 0 | 0 | 0 | 0 |  |
| P03R | 4 | 5 | 5 | 0 | 0 | 0 | 0 | 0 |  |
| P05 | 3 | 8 | 7 | 1 | 0 | 0 | 0 | 0 | amount differs from BSID (1) |
| P05R | 3 | 6 | 5 | 1 | 0 | 0 | 0 | 0 | amount differs from BSID (1) |
| P06 | 5 | 17 | 17 | 0 | 0 | 0 | 0 | 0 |  |
| P07 | 3 | 3 | 0 | 1 | 0 | 2 | 0 | 0 | No BSID match found (2); invoice of another customer than the sender (1) |
| P08 | 3 | 8 | 0 | 8 | 0 | 0 | 0 | 0 | amount differs from BSID (8) |
| R01 | 18 | 18 | 15 | 3 | 0 | 0 | 0 | 0 | amount differs from BSID (2); Possible OCR misread (1) |
| R02 | 5 | 5 | 4 | 1 | 0 | 0 | 0 | 0 | amount differs from BSID (1) |
| R03 | 14 | 154 | 119 | 34 | 0 | 1 | 0 | 0 | amount differs from BSID (25); Several open items carry this number (9); No BSID match found (1) |
| R04 | 8 | 8 | 0 | 0 | 0 | 8 | 0 | 0 | No BSID match found (8) |
| R05 | 7 | 11 | 9 | 2 | 0 | 0 | 0 | 0 | amount differs from BSID (1); amount / currency differs from BSID (1) |
| R06 | 4 | 4 | 0 | 4 | 0 | 0 | 0 | 0 | invoice of another customer than the sender (4) |
| R07 | 7 | 7 | 0 | 7 | 0 | 0 | 0 | 0 | amount differs from BSID (6); Several open items carry this number (1) |
| R08 | 6 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |  |
| R09 | 6 | 13 | 11 | 2 | 0 | 0 | 0 | 0 | amount differs from BSID (1); Several open items carry this number (1) |
| R10 | 6 | 21 | 19 | 2 | 0 | 0 | 0 | 0 | Several open items carry this number (2) |
| R11 | 4 | 4 | 3 | 1 | 0 | 0 | 0 | 0 | amount differs from BSID (1) |
| R12 | 5 | 5 | 0 | 5 | 0 | 0 | 0 | 0 | No invoice number - matched by amount (5) |
| R13 | 4 | 8 | 0 | 8 | 0 | 0 | 0 | 0 | No invoice number - matched by amount (8) |
| R14 | 4 | 4 | 2 | 2 | 0 | 0 | 0 | 0 | amount / currency differs from BSID (1); amount differs from BSID (1) |
| R16 | 5 | 5 | 0 | 0 | 0 | 5 | 0 | 0 | No BSID match found (5) |
| R17 | 4 | 4 | 0 | 4 | 0 | 0 | 0 | 0 | Several open items carry this number (4) |
| R18 | 4 | 4 | 0 | 4 | 0 | 0 | 0 | 0 | Payment block on the open item (4); Several open items carry this number (1) |
| R19 | 5 | 7 | 4 | 2 | 0 | 1 | 0 | 0 | amount differs from BSID (1); No BSID match found (1); Several open items carry this number (1) |
| R20 | 4 | 9 | 9 | 0 | 0 | 0 | 0 | 0 |  |
| R21 | 7 | 15 | 11 | 3 | 0 | 1 | 0 | 0 | amount differs from BSID (2); No BSID match found (1); invoice of another customer than the sender (1) |
| R22 | 6 | 13 | 13 | 0 | 0 | 0 | 0 | 0 |  |
| R23 | 3 | 7 | 6 | 1 | 0 | 0 | 0 | 0 | amount differs from BSID (1) |
| R24 | 6 | 28 | 0 | 0 | 0 | 0 | 28 | 0 | duplicate: same invoice, customer, amount, currency and sender domain (28) |
| R25 | 6 | 12 | 8 | 1 | 0 | 0 | 3 | 0 | duplicate: same invoice, customer, amount, currency and sender domain (3); amount differs from BSID (1) |
| R26 | 4 | 4 | 0 | 3 | 0 | 1 | 0 | 0 | amount differs from BSID (3); No BSID match found (1) |
| R27 | 4 | 4 | 0 | 4 | 0 | 0 | 0 | 0 | amount differs from BSID (4) |
| R28 | 3 | 3 | 0 | 3 | 0 | 0 | 0 | 0 | No invoice number - matched by amount (3) |
| R29 | 5 | 10 | 8 | 2 | 0 | 0 | 0 | 0 | amount differs from BSID (2) |
| R30 | 3 | 5 | 5 | 0 | 0 | 0 | 0 | 0 |  |
| R31 | 5 | 5 | 3 | 2 | 0 | 0 | 0 | 0 | amount differs from BSID (1); Several open items carry this number (1) |
| R32 | 5 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |  |

## Customer identification

Identified for **215 of 217** in-scope e-mails (99.1 %). Method used: INVOICE 179, SENDER_ADDRESS 36, none 2.

| Checked against | E-mails where it is known | Same customer |
|---|---|---|
| sender address in ADR6 | 212 | **97.6 %** (207) |
| quoted customer number | 81 | **98.8 %** (80) |
| customers of exactly matched invoices | 186 | **99.5 %** (185) |

Both checks count a payer relationship (KNVP RG, e.g. a holding company paying for its subsidiary) as the same customer. The row's customer is the OWNER of the matched invoice; when the sender is a different, unrelated customer the row goes to review ("Invoice belongs to customer X, but the e-mail comes from customer Y"): 6 e-mails - R06-0056, R06-0055, R06-0054, R21-0123, P07-0212, R06-0053.

Not identified (unknown sender, no unique invoice owner): R19-0115, R19-0113.

## Checks

- **JP-26-002271 (P03-0193)** -> customer 0000102419, 8300.00 SGD, match EXACT, confidence 92.00 % (FAST_PATH; formula 91.11 %), decision AUTO_PROCESS: **OK**
- **Duplicates found in the sample stream:** 31 rows in R24-0137, R24-0138, R24-0139, R24-0140, R24-0141, R24-0142, R25-0144, R25-0146, R25-0148 (the re-sent sample test - the same e-mail stored twice - is in tests/test_matching.py::test_resent_sample_becomes_duplicate).

  - R25-0146 line 1 (90032496) = duplicate of R25-0145#0: same invoice, customer, amount, currency and sender domain within 7 days
  - R24-0141 line 1 (MUM/2627/05208) = duplicate of R08-0067#0: same invoice, customer, amount, currency and sender domain within 7 days
  - R24-0142 line 1 (91005289) = duplicate of R03-0033#0: same invoice, customer, amount, currency and sender domain within 7 days
  - R24-0142 line 2 (91005245) = duplicate of R03-0033#1: same invoice, customer, amount, currency and sender domain within 7 days
  - R24-0142 line 3 (91004828) = duplicate of R03-0033#2: same invoice, customer, amount, currency and sender domain within 7 days
  - R24-0142 line 4 (91005531) = duplicate of R03-0033#3: same invoice, customer, amount, currency and sender domain within 7 days
  - R24-0142 line 5 (91005334) = duplicate of R03-0033#4: same invoice, customer, amount, currency and sender domain within 7 days
  - R24-0142 line 6 (SI22600492) = duplicate of R03-0033#5: same invoice, customer, amount, currency and sender domain within 7 days
  - R24-0142 line 7 (91005077) = duplicate of R03-0033#6: same invoice, customer, amount, currency and sender domain within 7 days
  - R24-0142 line 8 (91005108) = duplicate of R03-0033#7: same invoice, customer, amount, currency and sender domain within 7 days
  - R24-0137 line 1 (JP-26-002438) = duplicate of R01-0017#0: same invoice, customer, amount, currency and sender domain within 7 days
  - R24-0140 line 1 (SRV-400395) = duplicate of R03-0036#0: same invoice, customer, amount, currency and sender domain within 7 days
  - R24-0140 line 2 (UK-1043921) = duplicate of R03-0036#1: same invoice, customer, amount, currency and sender domain within 7 days
  - R24-0140 line 3 (UK-1043340) = duplicate of R03-0036#2: same invoice, customer, amount, currency and sender domain within 7 days
  - R24-0140 line 4 (UK-1043902) = duplicate of R03-0036#3: same invoice, customer, amount, currency and sender domain within 7 days
  - R24-0140 line 5 (UK-1043560) = duplicate of R03-0036#4: same invoice, customer, amount, currency and sender domain within 7 days
  - R24-0140 line 6 (UK-1043714) = duplicate of R03-0036#5: same invoice, customer, amount, currency and sender domain within 7 days
  - R24-0140 line 7 (SRV-400398) = duplicate of R03-0036#6: same invoice, customer, amount, currency and sender domain within 7 days
  - R24-0140 line 8 (UK-1043357) = duplicate of R03-0036#7: same invoice, customer, amount, currency and sender domain within 7 days
  - R24-0140 line 9 (UK-1043395) = duplicate of R03-0036#8: same invoice, customer, amount, currency and sender domain within 7 days

## Rows that are not auto-processed

| Sample | Set | Invoice | Customer | Level | Formula | Final | Source | Decision | Reason |
|---|---|---|---|---|---|---|---|---|---|
| R16-0103 | dev | 91012283 | 100970 | INVOICE_NONE | 0.00 | 0.00 | FORMULA | EXCEPTION | No BSID match found |
| R07-0063 | dev | SRV-200451 | 100690 | EXACT | 66.67 | 66.67 | FORMULA | MANUAL_REVIEW | amount 50.0525 % off |
| R04-0039 | dev | FA2026-08885 | 101102 | INVOICE_NONE | 0.00 | 0.00 | FORMULA | EXCEPTION | No BSID match found |
| R26-0150 | dev | 91005782 | 100574 | EXACT | 76.67 | 76.67 | FORMULA | MANUAL_REVIEW | amount 15.9664 % off |
| R13-0092 | dev | - | 101696 | AMOUNT_COMBINATION | 61.11 | 61.11 | FORMULA | MANUAL_REVIEW | No invoice number - matched by amount (2 invoice(s), difference -2616.000 INR) |
| R13-0092 | dev | - | 101696 | AMOUNT_COMBINATION | 56.67 | 56.67 | FORMULA | MANUAL_REVIEW | No invoice number - matched by amount (2 invoice(s), difference -2616.000 INR) |
| R03-0030 | dev | MUM/2627/04220 | 101947 | EXACT | 57.78 | 57.78 | FORMULA | MANUAL_REVIEW | amount 50.0000 % off |
| R03-0030 | dev | MUM/2627/04817 | 101947 | EXACT | 66.67 | 66.67 | FORMULA | MANUAL_REVIEW | amount 81.8457 % off |
| R03-0030 | dev | MUM/2526/04144 | 101947 | EXACT | 57.78 | 57.78 | FORMULA | MANUAL_REVIEW | amount 50.4018 % off |
| R03-0030 | dev | MUM/2627/04519 | 101947 | EXACT | 66.67 | 66.67 | FORMULA | MANUAL_REVIEW | amount 84.8073 % off |
| R03-0030 | dev | MUM/2627/04359 | 101947 | EXACT | 62.22 | 62.22 | FORMULA | MANUAL_REVIEW | amount 40.0009 % off |
| R03-0030 | dev | MUM/2526/04157 | 101947 | EXACT | 57.78 | 57.78 | FORMULA | MANUAL_REVIEW | amount 40.0009 % off |
| R03-0030 | dev | MUM/2627/04511 | 101947 | EXACT | 62.22 | 62.22 | FORMULA | MANUAL_REVIEW | amount 60.0000 % off |
| R03-0030 | dev | MUM/2526/04183 | 101947 | EXACT | 57.78 | 57.78 | FORMULA | MANUAL_REVIEW | amount 25.0000 % off |
| R03-0030 | dev | MUM/2627/04266 | 101947 | EXACT | 62.22 | 62.22 | FORMULA | MANUAL_REVIEW | amount 75.0000 % off |
| R03-0030 | dev | MUM/2627/04316 | 101947 | EXACT | 62.22 | 62.22 | FORMULA | MANUAL_REVIEW | amount 49.9602 % off |
| R03-0030 | dev | MUM/2627/04203 | 101947 | EXACT | 57.78 | 57.78 | FORMULA | MANUAL_REVIEW | amount 76.6385 % off |
| R03-0030 | dev | MUM/2627/05121 | 101947 | EXACT | 66.67 | 66.67 | FORMULA | MANUAL_REVIEW | amount 25.0001 % off |
| R03-0030 | dev | MUM/2627/04229 | 101947 | EXACT | 57.78 | 57.78 | FORMULA | MANUAL_REVIEW | amount 25.0000 % off |
| R03-0030 | dev | MUM/2627/05193 | 101947 | EXACT | 66.67 | 66.67 | FORMULA | MANUAL_REVIEW | amount 50.0116 % off |
| R13-0094 | dev | - | 102019 | AMOUNT_COMBINATION | 61.11 | 61.11 | FORMULA | MANUAL_REVIEW | No invoice number - matched by amount (2 invoice(s), difference -125.140 AED) |
| R13-0094 | dev | - | 102019 | AMOUNT_COMBINATION | 56.67 | 56.67 | FORMULA | MANUAL_REVIEW | No invoice number - matched by amount (2 invoice(s), difference -125.140 AED) |
| R04-0045 | dev | 9100551 | 101028 | INVOICE_NONE | 0.00 | 0.00 | FORMULA | EXCEPTION | No BSID match found |
| R29-0163 | dev | MUM/2627/04398 | 102009 | EXACT | 76.67 | 76.67 | FORMULA | MANUAL_REVIEW | amount 8.4742 % off |
| R12-0090 | dev | - | 100889 | AMOUNT_COMBINATION | 61.11 | 61.11 | FORMULA | MANUAL_REVIEW | No invoice number - matched by amount (1 invoice(s), difference 0.000 CHF) |
| R17-0107 | dev | 90032761 | 100586 | EXACT | 99.72 | 99.72 | FORMULA | MANUAL_REVIEW | Several open items carry this number |
| R12-0089 | dev | - | 102178 | AMOUNT_COMBINATION | 55.56 | 55.56 | FORMULA | MANUAL_REVIEW | No invoice number - matched by amount (1 invoice(s), difference 0.000 JPY) |
| R03-0037 | dev | SRV-200491 | 100943 | EXACT | 61.11 | 61.11 | FORMULA | MANUAL_REVIEW | amount 62.6143 % off |
| R03-0037 | dev | 91004764 | 100943 | EXACT | 85.56 | 92.00 | FAST_PATH | MANUAL_REVIEW | Several open items carry this number |
| R03-0037 | dev | 91004889 | 100943 | EXACT | 56.67 | 56.67 | FORMULA | MANUAL_REVIEW | amount 75.0000 % off |
| R03-0037 | dev | 91005566 | 100943 | EXACT | 61.11 | 61.11 | FORMULA | MANUAL_REVIEW | amount 49.9876 % off |
| R03-0037 | dev | 122600314 | 100943 | INVOICE_NONE | 0.00 | 0.00 | FORMULA | EXCEPTION | No BSID match found |
| R18-0108 | dev | 91005510 | 100690 | EXACT | 100.00 | 100.00 | FORMULA | MANUAL_REVIEW | Payment block on the open item (ZLSPR = R); Several open items carry this number |
| R13-0093 | heldout | - | 101147 | AMOUNT_COMBINATION | 55.56 | 55.56 | FORMULA | MANUAL_REVIEW | No invoice number - matched by amount (2 invoice(s), difference 10.210 EUR) |
| R13-0093 | heldout | - | 101147 | AMOUNT_COMBINATION | 55.56 | 55.56 | FORMULA | MANUAL_REVIEW | No invoice number - matched by amount (2 invoice(s), difference 10.210 EUR) |
| P07-0214 | heldout | 90039201 | 100352 | INVOICE_NONE | 0.00 | 0.00 | FORMULA | EXCEPTION | No BSID match found |
| R25-0145 | heldout | SRV-100387 | 100318 | EXACT | 76.67 | 76.67 | FORMULA | MANUAL_REVIEW | amount 10.0000 % off |
| R29-0161 | dev | MUM/2627/04244 | 101696 | EXACT | 77.78 | 77.78 | FORMULA | MANUAL_REVIEW | amount 8.4746 % off |
| P08-0215 | dev | 90032229 | 100438 | EXACT | 66.67 | 66.67 | FORMULA | MANUAL_REVIEW | amount 66.6667 % off |
| P08-0215 | dev | 90032229 | 100438 | EXACT | 66.67 | 66.67 | FORMULA | MANUAL_REVIEW | amount 66.6667 % off |
| P08-0215 | dev | 90032229 | 100438 | EXACT | 66.67 | 66.67 | FORMULA | MANUAL_REVIEW | amount 66.6667 % off |
| R03-0033 | dev | 91005334 | 100645 | EXACT | 66.67 | 66.67 | FORMULA | MANUAL_REVIEW | amount 28.0399 % off |
| R25-0146 | dev | 90032496 | 100318 | EXACT | 94.44 | 94.44 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R19-0112 | dev | JP-26-002358 | 102469 | EXACT | 51.11 | 51.11 | FORMULA | MANUAL_REVIEW | amount 75.0000 % off |
| R18-0109 | dev | JP-26-002589 | 102203 | EXACT | 99.72 | 99.72 | FORMULA | MANUAL_REVIEW | Payment block on the open item (ZLSPR = R) |
| R03-0026 | heldout | MUM/2627/04352 | 102123 | EXACT | 56.67 | 56.67 | FORMULA | MANUAL_REVIEW | amount 30.0000 % off |
| R19-0115 | dev | 5162600347 | - | INVOICE_NONE | 0.00 | 0.00 | FORMULA | EXCEPTION | No BSID match found |
| R28-0158 | dev | - | 100834 | AMOUNT_COMBINATION | 56.67 | 56.67 | FORMULA | MANUAL_REVIEW | No invoice number - matched by amount (1 invoice(s), difference 0.000 EUR) |
| R01-0005 | dev | UK-1043875 | 101494 | EXACT | 66.67 | 66.67 | FORMULA | MANUAL_REVIEW | amount 40.0011 % off |
| R31-0170 | heldout | JP-25-002226 | 102203 | EXACT | 57.50 | 57.50 | FORMULA | MANUAL_REVIEW | amount 60.1092 % off |
| R27-0155 | heldout | JP-26-002326 | 102300 | EXACT | 56.67 | 56.67 | FORMULA | MANUAL_REVIEW | amount 49.8985 % off |
| R07-0057 | dev | JP-26-002707 | 102263 | EXACT | 66.39 | 66.39 | FORMULA | MANUAL_REVIEW | amount 50.0000 % off |
| R28-0159 | heldout | - | 101102 | AMOUNT_COMBINATION | 55.56 | 55.56 | FORMULA | MANUAL_REVIEW | No invoice number - matched by amount (1 invoice(s), difference 0.000 EUR) |
| R26-0152 | dev | SI52600314 | 102203 | EXACT | 77.50 | 77.50 | FORMULA | MANUAL_REVIEW | amount 9.0909 % off |
| R26-0149 | dev | MUNI2627/04977 | 101721 | INVOICE_NONE | 0.00 | 0.00 | FORMULA | EXCEPTION | No BSID match found |
| R06-0056 | dev | 90032567 | 102419 | EXACT | 62.80 | 62.80 | FORMULA | MANUAL_REVIEW | Invoice belongs to customer 102419 (Pacific Rim Traders Pte. Ltd.), but the e-mail comes from customer 101519 (Oakridge Pharmaceuticals UK Ltd) |
| R06-0055 | heldout | 90032587 | 100352 | EXACT | 63.27 | 63.27 | FORMULA | MANUAL_REVIEW | Invoice belongs to customer 100352 (Blue Ridge Hardware LLC), but the e-mail comes from customer 100147 (Meridian Holdings Inc. Corporate Treasury) |
| R24-0141 | dev | MUM/2627/05208 | 101688 | EXACT | 93.33 | 93.33 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R24-0142 | heldout | 91005289 | 100645 | EXACT | 100.00 | 100.00 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R24-0142 | heldout | 91005245 | 100645 | EXACT | 100.00 | 100.00 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R24-0142 | heldout | 91004828 | 100645 | EXACT | 91.11 | 92.00 | FAST_PATH | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R24-0142 | heldout | 91005531 | 100645 | EXACT | 100.00 | 100.00 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R24-0142 | heldout | 91005334 | 100645 | EXACT | 66.67 | 66.67 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R24-0142 | heldout | SI22600492 | 100645 | EXACT | 100.00 | 100.00 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R24-0142 | heldout | 91005077 | 100645 | EXACT | 100.00 | 100.00 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R24-0142 | heldout | 91005108 | 100645 | EXACT | 100.00 | 100.00 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| P08-0216 | dev | SI42600379 | 101401 | EXACT | 66.67 | 66.67 | FORMULA | MANUAL_REVIEW | amount 66.6667 % off |
| P08-0216 | dev | SI42600379 | 101401 | EXACT | 66.67 | 66.67 | FORMULA | MANUAL_REVIEW | amount 66.6667 % off |
| P08-0216 | dev | SI42600379 | 101401 | EXACT | 66.67 | 66.67 | FORMULA | MANUAL_REVIEW | amount 66.6667 % off |
| R03-0034 | dev | 91004752 | 101068 | EXACT | 57.78 | 57.78 | FORMULA | MANUAL_REVIEW | amount 527.9274 % off |
| R03-0034 | dev | 91005266 | 101068 | EXACT | 66.67 | 91.00 | FAST_PATH | MANUAL_REVIEW | Several open items carry this number |
| R03-0034 | dev | 91004762 | 101068 | EXACT | 57.78 | 57.78 | FORMULA | MANUAL_REVIEW | amount 43.2297 % off |
| R03-0034 | dev | 91004753 | 101068 | EXACT | 57.78 | 57.78 | FORMULA | MANUAL_REVIEW | amount 526.4931 % off |
| R01-0009 | heldout | S112600517 | 100422 | NEAR | 88.33 | 88.33 | FORMULA | MANUAL_REVIEW | Possible OCR misread (I read as 1) |
| R31-0172 | dev | 91005124 | 100801 | EXACT | 100.00 | 100.00 | FORMULA | MANUAL_REVIEW | Several open items carry this number |
| R03-0028 | dev | 90031538 | 100422 | EXACT | 95.56 | 95.56 | FORMULA | MANUAL_REVIEW | Several open items carry this number |
| R03-0028 | dev | 90031542 | 100422 | EXACT | 95.56 | 95.56 | FORMULA | MANUAL_REVIEW | Several open items carry this number |
| R03-0028 | dev | 90032428 | 100422 | EXACT | 66.67 | 66.67 | FORMULA | MANUAL_REVIEW | amount 38.0711 % off |
| R03-0028 | dev | 90031244 | 100422 | EXACT | 57.78 | 57.78 | FORMULA | MANUAL_REVIEW | amount 59.9999 % off |
| R03-0028 | dev | 90031557 | 100422 | EXACT | 95.56 | 95.56 | FORMULA | MANUAL_REVIEW | Several open items carry this number |
| R16-0100 | dev | UK-1048799 | 101494 | INVOICE_NONE | 0.00 | 0.00 | FORMULA | EXCEPTION | No BSID match found |
| R27-0156 | dev | UK-1043670 | 101519 | EXACT | 66.67 | 66.67 | FORMULA | MANUAL_REVIEW | amount 50.0000 % off |
| R04-0044 | dev | MUM/2627/0422 | 101688 | INVOICE_NONE | 0.00 | 0.00 | FORMULA | EXCEPTION | No BSID match found |
| R16-0102 | dev | MUM/2627/01606 | 102077 | INVOICE_NONE | 0.00 | 0.00 | FORMULA | EXCEPTION | No BSID match found |
| R27-0153 | dev | MUM/2526/04136 | 101640 | EXACT | 57.78 | 57.78 | FORMULA | MANUAL_REVIEW | amount 50.0022 % off |
| R24-0137 | dev | JP-26-002438 | 102338 | EXACT | 100.00 | 100.00 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R04-0042 | dev | UK-1044387 | 101611 | INVOICE_NONE | 0.00 | 0.00 | FORMULA | EXCEPTION | No BSID match found |
| R07-0061 | dev | 90031557 | 100574 | EXACT | 66.67 | 66.67 | FORMULA | MANUAL_REVIEW | Several open items carry this number |
| R24-0140 | dev | SRV-400395 | 101345 | EXACT | 100.00 | 100.00 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R24-0140 | dev | UK-1043921 | 101345 | EXACT | 100.00 | 100.00 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R24-0140 | dev | UK-1043340 | 101345 | EXACT | 91.11 | 92.00 | FAST_PATH | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R24-0140 | dev | UK-1043902 | 101345 | EXACT | 100.00 | 100.00 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R24-0140 | dev | UK-1043560 | 101345 | EXACT | 100.00 | 100.00 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R24-0140 | dev | UK-1043714 | 101345 | EXACT | 100.00 | 100.00 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R24-0140 | dev | SRV-400398 | 101345 | EXACT | 100.00 | 100.00 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R24-0140 | dev | UK-1043357 | 101345 | EXACT | 95.56 | 95.56 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R24-0140 | dev | UK-1043395 | 101345 | EXACT | 95.56 | 95.56 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R24-0140 | dev | UK-1043717 | 101345 | EXACT | 100.00 | 100.00 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R24-0140 | dev | UK-1043520 | 101345 | EXACT | 100.00 | 100.00 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R24-0140 | dev | UK-1043915 | 101345 | EXACT | 100.00 | 100.00 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R27-0154 | dev | MUM/2627/04645 | 101640 | EXACT | 66.67 | 66.67 | FORMULA | MANUAL_REVIEW | amount 74.2518 % off |
| R01-0014 | dev | 90031240 | 100159 | EXACT | 57.78 | 57.78 | FORMULA | MANUAL_REVIEW | amount 49.9958 % off |
| R05-0052 | dev | JP26002293 | 102366 | EXACT | 62.22 | 62.22 | FORMULA | MANUAL_REVIEW | amount 50.0000 % off |
| R06-0054 | dev | 91005730 | 100943 | EXACT | 87.78 | 87.78 | FORMULA | MANUAL_REVIEW | Invoice belongs to customer 100943 (Van der Berg Logistics B.V.), but the e-mail comes from customer 100740 (Mueller & Soehne Maschinenbau KG) |
| R21-0123 | heldout | SRV-300475 | 101947 | INVOICE_NONE | 0.00 | 0.00 | FORMULA | EXCEPTION | No BSID match found |
| R21-0123 | heldout | MUM/2627/04869 | 101840 | EXACT | 63.16 | 63.16 | FORMULA | MANUAL_REVIEW | Invoice belongs to customer 101840 (Bharat Infra Projects Ltd.), but the e-mail comes from customer 101947 (Ganga Paper Mills Ltd.) |
| R21-0123 | heldout | MUM/2627/04531 | 101947 | EXACT | 62.22 | 62.22 | FORMULA | MANUAL_REVIEW | amount 5900.3394 % off |
| R12-0086 | dev | - | 100789 | AMOUNT_COMBINATION | 61.11 | 61.11 | FORMULA | MANUAL_REVIEW | No invoice number - matched by amount (1 invoice(s), difference 0.000 EUR) |
| R13-0091 | dev | - | 100690 | AMOUNT_COMBINATION | 61.11 | 61.11 | FORMULA | MANUAL_REVIEW | No invoice number - matched by amount (2 invoice(s), difference 8.630 EUR) |
| R13-0091 | dev | - | 100690 | AMOUNT_COMBINATION | 61.11 | 61.11 | FORMULA | MANUAL_REVIEW | No invoice number - matched by amount (2 invoice(s), difference 8.630 EUR) |
| R18-0110 | heldout | MUM/2627/04324 | 101894 | EXACT | 100.00 | 100.00 | FORMULA | MANUAL_REVIEW | Payment block on the open item (ZLSPR = R) |
| R09-0071 | dev | UK-1043303 | 101584 | EXACT | 52.22 | 52.22 | FORMULA | MANUAL_REVIEW | amount 49.9856 % off |
| R24-0138 | dev | 91005801 | 101028 | EXACT | 93.33 | 93.33 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R10-0079 | dev | 90031260 | 100147 | EXACT | 99.72 | 99.72 | FORMULA | MANUAL_REVIEW | Several open items carry this number |
| R21-0124 | dev | FA2025-08822 | 101227 | EXACT | 57.78 | 57.78 | FORMULA | MANUAL_REVIEW | amount 74.9713 % off |
| R04-0043 | heldout | UK-103419 | 101387 | INVOICE_NONE | 0.00 | 0.00 | FORMULA | EXCEPTION | No BSID match found |
| P08-0217 | heldout | SI22600424 | 100645 | EXACT | 66.67 | 66.67 | FORMULA | MANUAL_REVIEW | amount 50.0000 % off |
| P08-0217 | heldout | SI22600424 | 100645 | EXACT | 66.67 | 66.67 | FORMULA | MANUAL_REVIEW | amount 50.0000 % off |
| R04-0040 | heldout | 9003155 | 100159 | INVOICE_NONE | 0.00 | 0.00 | FORMULA | EXCEPTION | No BSID match found |
| R14-0097 | heldout | JP-26-002696 | 102247 | EXACT | 66.39 | 66.39 | FORMULA | MANUAL_REVIEW | amount / currency differs |
| R03-0031 | dev | FA2026-09085 | 101264 | EXACT | 61.11 | 61.11 | FORMULA | MANUAL_REVIEW | amount 81.7818 % off |
| R17-0104 | dev | 90031615 | 100889 | EXACT | 100.00 | 100.00 | FORMULA | MANUAL_REVIEW | Several open items carry this number |
| R11-0083 | dev | 90031505 | 100438 | EXACT | 72.22 | 72.22 | FORMULA | MANUAL_REVIEW | amount 10.0000 % off |
| R04-0038 | dev | MUM/2627/0500 | 101721 | INVOICE_NONE | 0.00 | 0.00 | FORMULA | EXCEPTION | No BSID match found |
| R28-0157 | dev | - | 102019 | AMOUNT_COMBINATION | 61.11 | 61.11 | FORMULA | MANUAL_REVIEW | No invoice number - matched by amount (1 invoice(s), difference 0.000 USD) |
| R26-0151 | heldout | MUM/2627/04656 | 101688 | EXACT | 76.67 | 76.67 | FORMULA | MANUAL_REVIEW | amount 10.7143 % off |
| R03-0032 | heldout | 91005075 | 100740 | EXACT | 94.44 | 94.44 | FORMULA | MANUAL_REVIEW | Several open items carry this number |
| R03-0032 | heldout | 91005180 | 100740 | EXACT | 94.44 | 94.44 | FORMULA | MANUAL_REVIEW | Several open items carry this number |
| R07-0059 | heldout | 90032449 | 100318 | EXACT | 61.11 | 61.11 | FORMULA | MANUAL_REVIEW | amount 50.0000 % off |
| P07-0212 | dev | MUM/2627/04999 | 101721 | EXACT | 63.11 | 63.11 | FORMULA | MANUAL_REVIEW | Invoice belongs to customer 101721 (Konkan Auto Components Pvt. Ltd.), but the e-mail comes from customer 101947 (Ganga Paper Mills Ltd.) |
| R19-0113 | dev | 90032556 | 100586 | EXACT | 88.61 | 92.00 | FAST_PATH | MANUAL_REVIEW | Several open items carry this number |
| R09-0072 | heldout | 91005515 | 100690 | EXACT | 86.67 | 86.67 | FORMULA | MANUAL_REVIEW | Several open items carry this number |
| R07-0062 | heldout | 91005446 | 100586 | EXACT | 66.39 | 66.39 | FORMULA | MANUAL_REVIEW | amount 30.0160 % off |
| R25-0144 | dev | MUM/2627/05155 | 101688 | EXACT | 100.00 | 100.00 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R03-0029 | heldout | 91005497 | 100690 | EXACT | 100.00 | 100.00 | FORMULA | MANUAL_REVIEW | Several open items carry this number |
| R03-0029 | heldout | 91005364 | 100690 | EXACT | 100.00 | 100.00 | FORMULA | MANUAL_REVIEW | Several open items carry this number |
| P07-0213 | dev | 90039164 | 100411 | INVOICE_NONE | 0.00 | 0.00 | FORMULA | EXCEPTION | No BSID match found |
| R16-0101 | heldout | JP-26-001724 | 102419 | INVOICE_NONE | 0.00 | 0.00 | FORMULA | EXCEPTION | No BSID match found |
| R12-0088 | heldout | - | 101519 | AMOUNT_COMBINATION | 61.11 | 61.11 | FORMULA | MANUAL_REVIEW | No invoice number - matched by amount (1 invoice(s), difference 0.000 GBP) |
| R17-0106 | heldout | 90032216 | 100380 | EXACT | 100.00 | 100.00 | FORMULA | MANUAL_REVIEW | Several open items carry this number |
| R24-0139 | heldout | FA2026-09035 | 101264 | EXACT | 90.00 | 92.00 | FAST_PATH | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R24-0139 | heldout | FA2026-09085 | 101264 | EXACT | 61.11 | 61.11 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R24-0139 | heldout | SRV-600356 | 101264 | EXACT | 94.44 | 94.44 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R24-0139 | heldout | FA2026-09116 | 101264 | EXACT | 94.44 | 94.44 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R24-0139 | heldout | FA2026-09135 | 101264 | EXACT | 94.44 | 94.44 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R06-0053 | dev | 91005417 | 101193 | EXACT | 62.84 | 62.84 | FORMULA | MANUAL_REVIEW | Invoice belongs to customer 101193 (Techniques Avancees du Nord SAS), but the e-mail comes from customer 100932 (Lindqvist Industri AB) |
| R10-0078 | heldout | 91004839 | 100789 | EXACT | 91.11 | 92.00 | FAST_PATH | MANUAL_REVIEW | Several open items carry this number |
| R07-0058 | dev | MUM/2627/05203 | 101721 | EXACT | 66.67 | 66.67 | FORMULA | MANUAL_REVIEW | amount 60.0000 % off |
| R17-0105 | dev | 90032216 | 100932 | EXACT | 100.00 | 100.00 | FORMULA | MANUAL_REVIEW | Several open items carry this number |
| R16-0099 | dev | FA2026-09909 | 101227 | INVOICE_NONE | 0.00 | 0.00 | FORMULA | EXCEPTION | No BSID match found |
| R18-0111 | dev | 90032044 | 100517 | EXACT | 100.00 | 100.00 | FORMULA | MANUAL_REVIEW | Payment block on the open item (ZLSPR = R) |
| R07-0060 | dev | JP-26-002272 | 102263 | EXACT | 61.94 | 61.94 | FORMULA | MANUAL_REVIEW | amount 40.0000 % off |
| R04-0041 | dev | 91004868 | 101028 | INVOICE_NONE | 0.00 | 0.00 | FORMULA | EXCEPTION | No BSID match found |
| P05-0205 | heldout | MUM/2526/04128 | 101947 | EXACT | 57.78 | 57.78 | FORMULA | MANUAL_REVIEW | amount 30.0001 % off |
| R02-0020 | dev | JP-26-002548 | 102338 | EXACT | 66.67 | 66.67 | FORMULA | MANUAL_REVIEW | amount 99.9776 % off |
| R25-0148 | heldout | 90031381 | 100352 | EXACT | 95.56 | 95.56 | FORMULA | DUPLICATE | same invoice, customer, amount, currency and sender domain within 7 days |
| R12-0087 | dev | - | 101790 | AMOUNT_COMBINATION | 56.67 | 56.67 | FORMULA | MANUAL_REVIEW | No invoice number - matched by amount (1 invoice(s), difference 0.000 INR) |
| R23-0136 | heldout | 91005138 | 101028 | EXACT | 66.67 | 66.67 | FORMULA | MANUAL_REVIEW | amount 39.9982 % off |
| R14-0098 | dev | 91005157 | 100889 | EXACT | 76.67 | 76.67 | FORMULA | MANUAL_REVIEW | amount 11.6390 % off |
| R05-0046 | dev | 90031968 | 100539 | EXACT | 61.11 | 61.11 | FORMULA | MANUAL_REVIEW | amount / currency differs |
| P02-0189 | heldout | FA2026-08987 | 101264 | EXACT | 56.67 | 56.67 | FORMULA | MANUAL_REVIEW | amount 73.9762 % off |
| P02-0189 | heldout | FA2026-09111 | 101264 | EXACT | 61.11 | 61.11 | FORMULA | MANUAL_REVIEW | amount 50.0000 % off |
| P05R-0206 | heldout | MUM/2526/04128 | 101947 | EXACT | 57.78 | 57.78 | FORMULA | MANUAL_REVIEW | amount 30.0001 % off |
