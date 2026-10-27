# M03 — classification report

234 sample e-mails (expected answer = folder prefix), business date 2026-10-28, sender check: ADR6 (laptop database). Run time 6 s.

A result counts as correct only when the label, both flags (contains remittance / contains PTP) and, for out of scope, the category are all right.

## Accuracy

| Method | Correct | Accuracy | Label only |
|---|---|---|---|
| Rules only (optimistic: keywords written while looking at these samples) | 234/234 | **100.0 %** | 100.0 % |
| Rules + model, 5-fold cross-validated (the model never judges an e-mail it learned from) | 234/234 | **100.0 %** | 100.0 % |
| Model alone, cross-validated (for comparison) | 222/234 | 94.9 % | 94.9 % |
| Hand-written e-mails (not samples), batch 1, rules only | 26/26 | 100.0 % | |
| Hand-written e-mails (not samples), batch 1, rules + model | 26/26 | 100.0 % | |
| Hand-written e-mails (not samples), batch 2, rules only | 18/18 | 100.0 % | |
| Hand-written e-mails (not samples), batch 2, rules + model | 18/18 | 100.0 % | |

About the hand-written e-mails: Hand-written e-mails NOT taken from data/samples (new wording) - a check beyond the samples, because the M03 keyword lists were written while looking at the samples. expected: REMITTANCE | PTP | MIXED | OUT_OF_SCOPE:<CATEGORY>. History (be honest when quoting the results): batch 1 (U01-U26) first run 23/26 rules + model, its misses led to two general fixes; batch 2 (U27-U44) written afterwards, first run rules only 8/18, rules + model 15/18, then its missed phrases were added to the keyword lists. Both batches are therefore no longer truly unseen: add a new batch before quoting a fresh number.

The model was asked for 3 of 234 samples (rules confidence below 70 %).

## Accuracy per type (expected type; PTP includes the P06 e-mails with payment + promise)

| Method | REMITTANCE | PTP | OUT_OF_SCOPE |
|---|---|---|---|
| Rules only | 184/184 | 33/33 | 17/17 |
| Rules + model, cross-validated | 184/184 | 33/33 | 17/17 |
| Model alone, cross-validated | 183/184 | 22/33 | 17/17 |

Model alone, cross-validated - misses (12); this is why the rules decide and the model is only asked when the rules are unsure:

- P01-0186: expected PTP, model said REMITTANCE
- P02-0188: expected PTP, model said REMITTANCE
- P02-0189: expected PTP, model said REMITTANCE
- P02-0191: expected PTP, model said REMITTANCE
- P03-0197: expected PTP, model said REMITTANCE
- P05R-0202: expected REMITTANCE, model said MIXED
- P06-0207: expected MIXED, model said REMITTANCE
- P06-0208: expected MIXED, model said REMITTANCE
- P06-0209: expected MIXED, model said REMITTANCE
- P06-0210: expected MIXED, model said REMITTANCE
- P06-0211: expected MIXED, model said REMITTANCE
- P08-0217: expected PTP, model said REMITTANCE

## Confusion matrix (rules + model, cross-validated)

| Expected \ Result | REMITTANCE | PTP | OUT_OF_SCOPE |
|---|---|---|---|
| REMITTANCE | 184 | 0 | 0 |
| PTP | 0 | 33 | 0 |
| OUT_OF_SCOPE | 0 | 0 | 17 |

## E-mails with remittance AND promise

| Sample | Label | Contains remittance | Contains PTP | Confidence | Correct |
|---|---|---|---|---|---|
| P03R-0194 | REMITTANCE | yes | no | 99.0 | ✅ |
| P03R-0196 | REMITTANCE | yes | no | 99.0 | ✅ |
| P03R-0198 | REMITTANCE | yes | no | 95.0 | ✅ |
| P03R-0200 | REMITTANCE | yes | no | 93.1 | ✅ |
| P05R-0202 | REMITTANCE | yes | no | 96.4 | ✅ |
| P05R-0204 | REMITTANCE | yes | no | 99.0 | ✅ |
| P05R-0206 | REMITTANCE | yes | no | 99.0 | ✅ |
| P06-0207 | PTP | yes | yes | 96.4 | ✅ |
| P06-0208 | PTP | yes | yes | 93.1 | ✅ |
| P06-0209 | PTP | yes | yes | 93.1 | ✅ |
| P06-0210 | PTP | yes | yes | 86.5 | ✅ |
| P06-0211 | PTP | yes | yes | 95.0 | ✅ |

P06 e-mails pay some invoices and promise the rest, so both flags must be set. P03R / P05R are the payments that follow an earlier promise (P03 / P05): their bodies and attachments contain only the payment (checked by reading all six), so the expected answer is REMITTANCE with no promise; linking them to the earlier promise is M10 (PTP kept).

## Per scenario (rules + model, cross-validated)

| Scenario | E-mails | Correct | Avg confidence |
|---|---|---|---|
| O01 | 3 | 3 | 93.1 |
| O02 | 3 | 3 | 79.0 |
| O03 | 2 | 2 | 73.7 |
| O04 | 2 | 2 | 96.4 |
| O05 | 3 | 3 | 87.6 |
| O06 | 2 | 2 | 74.7 |
| O07 | 2 | 2 | 86.5 |
| P01 | 9 | 9 | 96.7 |
| P02 | 6 | 6 | 96.0 |
| P03 | 4 | 4 | 98.2 |
| P03R | 4 | 4 | 96.5 |
| P05 | 3 | 3 | 96.9 |
| P05R | 3 | 3 | 98.1 |
| P06 | 5 | 5 | 92.8 |
| P07 | 3 | 3 | 98.7 |
| P08 | 3 | 3 | 96.1 |
| R01 | 18 | 18 | 97.0 |
| R02 | 5 | 5 | 91.8 |
| R03 | 14 | 14 | 97.2 |
| R04 | 8 | 8 | 97.7 |
| R05 | 7 | 7 | 96.4 |
| R06 | 4 | 4 | 95.8 |
| R07 | 7 | 7 | 94.7 |
| R08 | 6 | 6 | 90.0 |
| R09 | 6 | 6 | 95.4 |
| R10 | 6 | 6 | 95.2 |
| R11 | 4 | 4 | 97.9 |
| R12 | 5 | 5 | 86.8 |
| R13 | 4 | 4 | 92.8 |
| R14 | 4 | 4 | 96.0 |
| R16 | 5 | 5 | 98.6 |
| R17 | 4 | 4 | 93.2 |
| R18 | 4 | 4 | 96.4 |
| R19 | 5 | 5 | 95.8 |
| R20 | 4 | 4 | 95.6 |
| R21 | 7 | 7 | 98.5 |
| R22 | 6 | 6 | 91.9 |
| R23 | 3 | 3 | 97.1 |
| R24 | 6 | 6 | 95.3 |
| R25 | 6 | 6 | 99.0 |
| R26 | 4 | 4 | 96.4 |
| R27 | 4 | 4 | 98.5 |
| R28 | 3 | 3 | 88.2 |
| R29 | 5 | 5 | 99.0 |
| R30 | 3 | 3 | 96.1 |
| R31 | 5 | 5 | 97.5 |
| R32 | 5 | 5 | 98.3 |

## Misses (rules + model, cross-validated)

None.

## Where the model was asked

| Sample | Rules said | Model said | Final | Decision |
|---|---|---|---|---|
| O04-0226 | OUT_OF_SCOPE:GENERAL (63.2) | OUT_OF_SCOPE:GENERAL (0.964) | OUT_OF_SCOPE:GENERAL (96.4) | agrees with the rules |
| O04-0227 | OUT_OF_SCOPE:GENERAL (63.2) | OUT_OF_SCOPE:GENERAL (0.964) | OUT_OF_SCOPE:GENERAL (96.4) | agrees with the rules |
| O06-0232 | OUT_OF_SCOPE:HR (20.0) | OUT_OF_SCOPE:HR (0.683) | OUT_OF_SCOPE:HR (68.3) | agrees with the rules |

## Hand-written e-mails (rules + model trained on all samples)

| Id | Batch | Subject | Expected | Result | Confidence | Method | Correct | Signals |
|---|---|---|---|---|---|---|---|---|
| U01 | 1 | Funds sent | REMITTANCE | REMITTANCE | 73.6 | rules | ✅ | funds sent (remittance) |
| U02 | 1 | Settlement of your invoice UK-1043555 | REMITTANCE | REMITTANCE | 73.6 | rules | ✅ | we have paid (remittance) |
| U03 | 1 | Payment confirmation | REMITTANCE | REMITTANCE | 86.5 | rules | ✅ | payment advice (remittance), amount paid (remittance) |
| U04 | 1 | Ueberweisung | REMITTANCE | REMITTANCE | 81.1 | rules | ✅ | ueberwiesen (remittance), ueberweisung (remittance) |
| U05 | 1 | Virement effectue | REMITTANCE | REMITTANCE | 93.1 | rules | ✅ | nous avons regle (remittance), paiement effectue (remittance), virement (remittance) |
| U06 | 1 | Transferencia realizada | REMITTANCE | REMITTANCE | 81.1 | rules | ✅ | hemos pagado (remittance), transferencia (remittance) |
| U07 | 1 | Pagamento | REMITTANCE | REMITTANCE | 73.6 | rules | ✅ | pagamento efetuado (remittance) |
| U08 | 1 | お支払い完了のお知らせ | REMITTANCE | REMITTANCE | 73.6 | rules | ✅ | 振込みました (remittance) |
| U09 | 1 | Re: Statement of account | PTP | PTP | 81.1 | rules | ✅ | we will pay (ptp), date after business date (ptp) |
| U10 | 1 | Payment date for open items | PTP | PTP | 67.6 | rules+model | ✅ | payment reference (remittance), will be paid (ptp), date after business date (ptp) |
| U11 | 1 | Ihre Zahlungserinnerung | PTP | PTP | 81.1 | rules | ✅ | werden begleichen (ptp), date after business date (ptp) |
| U12 | 1 | Echeancier facture FA2026-09400 | PTP | PTP | 90.3 | rules | ✅ | engagement de paiement (ptp), nous paierons (ptp) |
| U13 | 1 | Pago pendiente | PTP | PTP | 93.1 | rules | ✅ | realizaremos el pago (ptp), efetuaremos (ptp), date after business date (ptp) |
| U14 | 1 | Previsao de pagamento | PTP | PTP | 81.1 | rules | ✅ | efetuaremos (ptp), date after business date (ptp) |
| U15 | 1 | お支払いについて | PTP | PTP | 63.2 | rules+model | ✅ | お支払い予定 (ptp) |
| U16 | 1 | Partial payment and plan | MIXED | MIXED | 81.1 | rules | ✅ | we have paid (remittance), has been paid (remittance), paid today (remittance), will be paid (ptp), date after business date (ptp) |
| U17 | 1 | Zahlung und Restzahlung | MIXED | MIXED | 73.6 | rules | ✅ | ueberwiesen (remittance), werden begleichen (ptp), date after business date (ptp) |
| U18 | 1 | Black Friday deals for finance teams | OUT_OF_SCOPE:MARKETING | OUT_OF_SCOPE:MARKETING | 63.2 | rules+model | ✅ | unsubscribe (oos:marketing) |
| U19 | 1 | Wrong item delivered - order 55120 | OUT_OF_SCOPE:CUSTOMER_SERVICE | OUT_OF_SCOPE:CUSTOMER_SERVICE | 65.5 | rules+model | ✅ | replacement (oos:customer_service), complaint (oos:customer_service) |
| U20 | 1 | Price request | OUT_OF_SCOPE:SALES_INQUIRY | OUT_OF_SCOPE:SALES_INQUIRY | 35.5 | rules+model | ✅ | price / lead time (oos:sales_inquiry) |
| U21 | 1 | Introduction | OUT_OF_SCOPE:GENERAL | OUT_OF_SCOPE:GENERAL | 20.0 | rules+model | ✅ | meeting request (oos:general) |
| U22 | 1 | Invoice 2026-7781 from Brightclean Facilities | OUT_OF_SCOPE:VENDOR_INVOICE | OUT_OF_SCOPE:VENDOR_INVOICE | 87.6 | rules | ✅ | bill to (oos:vendor_invoice), amount due (oos:vendor_invoice), tax invoice (oos:vendor_invoice), invoice file (oos:vendor_invoice) |
| U23 | 1 | Salary certificate request | OUT_OF_SCOPE:HR | OUT_OF_SCOPE:HR | 81.1 | rules | ✅ | payslip (oos:hr), job application (oos:hr) |
| U24 | 1 | Balance alert | OUT_OF_SCOPE:BANK_NOTIFICATION | OUT_OF_SCOPE:BANK_NOTIFICATION | 63.2 | rules+model | ✅ | fx / balance alert (oos:bank_notification), automated message (oos:bank_notification) |
| U25 | 1 | FW: payment | REMITTANCE | REMITTANCE | 73.6 | rules | ✅ | has been paid (remittance) |
| U26 | 1 | Query on invoice 90031888 | OUT_OF_SCOPE:CUSTOMER_SERVICE | OUT_OF_SCOPE:CUSTOMER_SERVICE | 32.4 | rules+model | ✅ | complaint (oos:customer_service) |
| U27 | 2 | Paid | REMITTANCE | REMITTANCE | 73.6 | rules | ✅ | has been paid (remittance) |
| U28 | 2 | Proof of payment | REMITTANCE | REMITTANCE | 73.6 | rules | ✅ | proof of payment (remittance) |
| U29 | 2 | Zahlungseingang folgt | REMITTANCE | REMITTANCE | 73.6 | rules | ✅ | wurde angewiesen (remittance) |
| U30 | 2 | Paiement facture FA2026-09333 | REMITTANCE | REMITTANCE | 81.1 | rules | ✅ | a ete payee (remittance), virement (remittance) |
| U31 | 2 | Comprobante | REMITTANCE | REMITTANCE | 81.1 | rules | ✅ | comprobante (remittance), transferencia (remittance) |
| U32 | 2 | 送金のご案内 | REMITTANCE | REMITTANCE | 73.6 | rules | ✅ | 振込みました (remittance) |
| U33 | 2 | Re: Overdue invoices | PTP | PTP | 73.6 | rules | ✅ | next payment run (ptp) |
| U34 | 2 | Payment next week | PTP | PTP | 81.1 | rules | ✅ | expect payment (ptp), date after business date (ptp) |
| U35 | 2 | Zahlung Rechnung 91004888 | PTP | PTP | 81.1 | rules | ✅ | voraussichtlich (ptp), date after business date (ptp) |
| U36 | 2 | Reglement prevu | PTP | PTP | 81.1 | rules | ✅ | est prevu (ptp), date after business date (ptp) |
| U37 | 2 | Fecha de pago | PTP | PTP | 81.1 | rules | ✅ | se pagara (ptp), date after business date (ptp) |
| U38 | 2 | Pagamento programado | PTP | PTP | 93.1 | rules | ✅ | se pagara (ptp), esta programado (ptp), date after business date (ptp) |
| U39 | 2 | Payment update | MIXED | MIXED | 81.1 | rules | ✅ | has been paid (remittance), paid today (remittance), will follow on (ptp), date after business date (ptp) |
| U40 | 2 | Your free trial is waiting | OUT_OF_SCOPE:MARKETING | OUT_OF_SCOPE:MARKETING | 63.2 | rules+model | ✅ | unsubscribe (oos:marketing) |
| U41 | 2 | Late delivery | OUT_OF_SCOPE:CUSTOMER_SERVICE | OUT_OF_SCOPE:CUSTOMER_SERVICE | 32.4 | rules+model | ✅ | complaint (oos:customer_service) |
| U42 | 2 | Rechnung RE-2026-5512 | OUT_OF_SCOPE:VENDOR_INVOICE | OUT_OF_SCOPE:VENDOR_INVOICE | 32.4 | rules+model | ✅ | amount due (oos:vendor_invoice) |
| U43 | 2 | Leave request | OUT_OF_SCOPE:HR | OUT_OF_SCOPE:HR | 20.0 | rules+model | ✅ | job application (oos:hr) |
| U44 | 2 | Scheduled maintenance | OUT_OF_SCOPE:BANK_NOTIFICATION | OUT_OF_SCOPE:BANK_NOTIFICATION | 86.5 | rules | ✅ | statement ready (oos:bank_notification), fx / balance alert (oos:bank_notification), automated message (oos:bank_notification) |
