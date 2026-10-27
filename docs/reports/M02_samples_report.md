# M02 — sample parsing report

234 sample e-mails, 188 attachments, run time 119 s (time saved by reusing identical files: 10.3 s, 6 files reused).

## Summary by file type

| Type | Files | Parsed | Skipped | Failed | Methods | Avg chars | Avg OCR conf | Avg ms (excl. reused) |
|---|---|---|---|---|---|---|---|---|
| container | 1 | 0 | 1 | 0 | container 1 | 0 | 0.0 | 0 |
| csv | 1 | 1 | 0 | 0 | csv 1 | 153 | 0.0 | 5 |
| docx | 22 | 22 | 0 | 0 | docx 22 | 559 | 0.0 | 25 |
| image | 29 | 29 | 0 | 0 | ocr 29 | 399 | 89.5 | 2850 |
| pdf | 117 | 117 | 0 | 0 | text 107, ocr 10 | 862 | 89.7 | 346 |
| xlsx | 18 | 18 | 0 | 0 | spreadsheet 18 | 253 | 0.0 | 29 |

## E-mail bodies

234 bodies; **51 body-only e-mails** (no attachment); 24 bodies contain a table (24 of the body-only ones).

## Every item

| Sample | File | Type | Body-only | Method | Status | Pages | Chars | OCR conf | Lang | Tables | ms | Reused | Note |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| O01-0218 | (body) | body | yes | body | PARSED |  | 182 |  | en | 0 | 0 |  |  |
| O01-0219 | (body) | body | yes | body | PARSED |  | 191 |  | en | 0 | 0 |  |  |
| O01-0220 | (body) | body | yes | body | PARSED |  | 180 |  | en | 0 | 0 |  |  |
| O02-0221 | (body) | body | yes | body | PARSED |  | 184 |  | en | 0 | 0 |  |  |
| O02-0222 | (body) | body | yes | body | PARSED |  | 180 |  | en | 0 | 0 |  |  |
| O02-0223 | (body) | body | yes | body | PARSED |  | 182 |  | en | 0 | 0 |  |  |
| O03-0224 | (body) | body | yes | body | PARSED |  | 134 |  | en | 0 | 0 |  |  |
| O03-0225 | (body) | body | yes | body | PARSED |  | 134 |  | en | 0 | 0 |  |  |
| O04-0226 | (body) | body | yes | body | PARSED |  | 176 |  | en | 0 | 0 |  |  |
| O04-0227 | (body) | body | yes | body | PARSED |  | 176 |  | en | 0 | 0 |  |  |
| O05-0228 | (body) | body |  | body | PARSED |  | 93 |  | en | 0 | 0 |  |  |
| O05-0228 | SINV-74512.pdf | pdf |  | text | PARSED | 1 | 289 |  | en | 1 | 2200 |  |  |
| O05-0229 | (body) | body |  | body | PARSED |  | 93 |  | en | 0 | 0 |  |  |
| O05-0229 | SINV-51743.pdf | pdf |  | text | PARSED | 1 | 289 |  | en | 1 | 34 |  |  |
| O05-0230 | (body) | body |  | body | PARSED |  | 94 |  | en | 0 | 0 |  |  |
| O05-0230 | SINV-71207.pdf | pdf |  | text | PARSED | 1 | 285 |  | en | 1 | 26 |  |  |
| O06-0231 | (body) | body | yes | body | PARSED |  | 75 |  | en | 0 | 0 |  |  |
| O06-0232 | (body) | body | yes | body | PARSED |  | 75 |  | en | 0 | 0 |  |  |
| O07-0233 | (body) | body | yes | body | PARSED |  | 166 |  | en | 0 | 0 |  |  |
| O07-0234 | (body) | body | yes | body | PARSED |  | 166 |  | en | 0 | 0 |  |  |
| P01-0178 | (body) | body |  | body | PARSED |  | 109 |  | en | 0 | 0 |  |  |
| P01-0178 | PTP_letter_PAY688234.pdf | pdf |  | text | PARSED | 1 | 847 |  | en | 0 | 99 |  |  |
| P01-0179 | (body) | body |  | body | PARSED |  | 119 |  | en | 0 | 0 |  |  |
| P01-0179 | Payment_Commitment_ZA-34406.pdf | pdf |  | text | PARSED | 1 | 405 |  | en | 0 | 41 |  |  |
| P01-0180 | (body) | body |  | body | PARSED |  | 104 |  | en | 0 | 0 |  |  |
| P01-0180 | Payment_Commitment_PV2095184.pdf | pdf |  | text | PARSED | 1 | 434 |  | en | 0 | 32 |  |  |
| P01-0181 | (body) | body | yes | body | PARSED |  | 127 |  | en | 0 | 0 |  |  |
| P01-0182 | (body) | body |  | body | PARSED |  | 108 |  | en | 0 | 0 |  |  |
| P01-0182 | PTP_letter_PV4470708.pdf | pdf |  | text | PARSED | 1 | 620 |  | en | 0 | 33 |  |  |
| P01-0183 | (body) | body | yes | body | PARSED |  | 162 |  | ja | 0 | 0 |  |  |
| P01-0184 | (body) | body |  | body | PARSED |  | 108 |  | en | 0 | 0 |  |  |
| P01-0184 | Payment_Commitment_PAY786057.pdf | pdf |  | text | PARSED | 1 | 798 |  | en | 0 | 34 |  |  |
| P01-0185 | (body) | body |  | body | PARSED |  | 112 |  | en | 0 | 0 |  |  |
| P01-0185 | PTP_letter_PAY932611.pdf | pdf |  | text | PARSED | 1 | 783 |  | en | 0 | 33 |  |  |
| P01-0186 | (body) | body |  | body | PARSED |  | 208 |  | de | 0 | 0 |  |  |
| P01-0186 | Zahlungszusage_PAY288853.pdf | pdf |  | text | PARSED | 1 | 867 |  | de | 0 | 39 |  |  |
| P02-0187 | (body) | body |  | body | PARSED |  | 138 |  | en | 0 | 0 |  |  |
| P02-0187 | Payment_Commitment_PAY142196.docx | docx |  | docx | PARSED |  | 461 |  | en | 1 | 140 |  |  |
| P02-0188 | (body) | body |  | body | PARSED |  | 242 |  | de | 0 | 0 |  |  |
| P02-0188 | Zahlungszusage_PAY418973.pdf | pdf |  | text | PARSED | 1 | 740 |  | de | 0 | 32 |  |  |
| P02-0189 | (body) | body |  | body | PARSED |  | 154 |  | es | 0 | 0 |  |  |
| P02-0189 | Compromiso_pago_RA-2026-5277.xlsx | xlsx |  | spreadsheet | PARSED | 1 | 361 |  | pt | 1 | 367 |  |  |
| P02-0190 | (body) | body |  | body | PARSED |  | 128 |  | en | 0 | 0 |  |  |
| P02-0190 | Payment_Commitment_PAY726368.pdf | pdf |  | text | PARSED | 1 | 433 |  | en | 0 | 28 |  |  |
| P02-0191 | (body) | body |  | body | PARSED |  | 154 |  | ja | 0 | 0 |  |  |
| P02-0191 | shiharai_yotei_ZA-81161.xlsx | xlsx |  | spreadsheet | PARSED | 1 | 217 |  | en | 1 | 10 |  |  |
| P02-0192 | (body) | body |  | body | PARSED |  | 121 |  | en | 0 | 0 |  |  |
| P02-0192 | Payment_Commitment_0411-197.docx | docx |  | docx | PARSED |  | 451 |  | en | 1 | 14 |  |  |
| P03-0193 | (body) | body |  | body | PARSED |  | 121 |  | en | 0 | 0 |  |  |
| P03-0193 | PTP_letter_PAY294056.pdf | pdf |  | text | PARSED | 1 | 820 |  | en | 0 | 35 |  |  |
| P03-0195 | (body) | body |  | body | PARSED |  | 105 |  | en | 0 | 0 |  |  |
| P03-0195 | PTP_letter_0411-263.pdf | pdf |  | text | PARSED | 1 | 595 |  | en | 0 | 37 |  |  |
| P03-0197 | (body) | body |  | body | PARSED |  | 134 |  | fr | 0 | 0 |  |  |
| P03-0197 | Engagement_paiement_1092-831.pdf | pdf |  | text | PARSED | 1 | 876 |  | fr | 0 | 37 |  |  |
| P03-0199 | (body) | body |  | body | PARSED |  | 129 |  | en | 0 | 0 |  |  |
| P03-0199 | Payment_Commitment_PAY701089.pdf | pdf |  | text | PARSED | 1 | 937 |  | en | 0 | 35 |  |  |
| P03R-0194 | (body) | body |  | body | PARSED |  | 93 |  | en | 0 | 0 |  |  |
| P03R-0194 | Payment_Advice_PAY203602.pdf | pdf |  | text | PARSED | 1 | 850 |  | en | 0 | 39 |  |  |
| P03R-0196 | (body) | body |  | body | PARSED |  | 95 |  | en | 0 | 0 |  |  |
| P03R-0196 | RA_0411-693.pdf | pdf |  | text | PARSED | 1 | 789 |  | en | 0 | 41 |  |  |
| P03R-0198 | (body) | body |  | body | PARSED |  | 59 |  | fr | 0 | 0 |  |  |
| P03R-0198 | Avis_de_paiement_1092-223.xlsx | xlsx |  | spreadsheet | PARSED | 1 | 183 |  | en | 1 | 14 |  |  |
| P03R-0200 | (body) | body | yes | body | PARSED |  | 241 |  | en | 1 | 0 |  |  |
| P05-0201 | (body) | body | yes | body | PARSED |  | 236 |  | pt | 1 | 0 |  |  |
| P05-0203 | (body) | body |  | body | PARSED |  | 144 |  | en | 0 | 0 |  |  |
| P05-0203 | PTP_letter_PV9970610.pdf | pdf |  | text | PARSED | 1 | 989 |  | en | 0 | 36 |  |  |
| P05-0205 | (body) | body |  | body | PARSED |  | 157 |  | en | 0 | 0 |  |  |
| P05-0205 | PTP_letter_ZA-50406.pdf | pdf |  | text | PARSED | 1 | 1071 |  | en | 0 | 60 |  |  |
| P05R-0202 | (body) | body |  | body | PARSED |  | 102 |  | pt | 0 | 0 |  |  |
| P05R-0202 | Aviso_de_pagamento_RA-2026-9867.pdf | pdf |  | text | PARSED | 1 | 909 |  | pt | 0 | 37 |  |  |
| P05R-0204 | (body) | body |  | body | PARSED |  | 88 |  | en | 0 | 0 |  |  |
| P05R-0204 | Payment_Advice_PV3722259.pdf | pdf |  | text | PARSED | 1 | 960 |  | en | 0 | 34 |  |  |
| P05R-0206 | (body) | body |  | body | PARSED |  | 78 |  | en | 0 | 0 |  |  |
| P05R-0206 | Remittance_Advice_ZA-58351.pdf | pdf |  | text | PARSED | 1 | 947 |  | en | 0 | 43 |  |  |
| P06-0207 | (body) | body |  | body | PARSED |  | 196 |  | en | 0 | 0 |  |  |
| P06-0207 | Payment_Advice_PAY921097.pdf | pdf |  | text | PARSED | 1 | 1018 |  | en | 0 | 42 |  |  |
| P06-0208 | (body) | body | yes | body | PARSED |  | 456 |  | de | 1 | 0 |  |  |
| P06-0209 | (body) | body | yes | body | PARSED |  | 285 |  | en | 1 | 0 |  |  |
| P06-0210 | (body) | body | yes | body | PARSED |  | 332 |  | de | 1 | 0 |  |  |
| P06-0211 | (body) | body |  | body | PARSED |  | 172 |  | pt | 0 | 0 |  |  |
| P06-0211 | Aviso_de_pagamento_RA-2026-9474.pdf | pdf |  | text | PARSED | 1 | 1050 |  | pt | 0 | 54 |  |  |
| P07-0212 | (body) | body |  | body | PARSED |  | 112 |  | en | 0 | 0 |  |  |
| P07-0212 | PTP_letter_ZA-24998.pdf | pdf |  | text | PARSED | 1 | 769 |  | en | 0 | 38 |  |  |
| P07-0213 | (body) | body |  | body | PARSED |  | 104 |  | en | 0 | 0 |  |  |
| P07-0213 | PTP_letter_0411-628.pdf | pdf |  | text | PARSED | 1 | 731 |  | en | 0 | 52 |  |  |
| P07-0214 | (body) | body |  | body | PARSED |  | 103 |  | en | 0 | 0 |  |  |
| P07-0214 | Payment_Commitment_0352-492.pdf | pdf |  | text | PARSED | 1 | 722 |  | en | 0 | 54 |  |  |
| P08-0215 | (body) | body |  | body | PARSED |  | 97 |  | en | 0 | 0 |  |  |
| P08-0215 | PTP_letter_RA-2026-3445.pdf | pdf |  | text | PARSED | 1 | 540 |  | en | 0 | 47 |  |  |
| P08-0216 | (body) | body | yes | body | PARSED |  | 105 |  | en | 0 | 0 |  |  |
| P08-0217 | (body) | body | yes | body | PARSED |  | 141 |  | de | 0 | 0 |  |  |
| R01-0001 | (body) | body |  | body | PARSED |  | 86 |  | en | 0 | 0 |  |  |
| R01-0001 | Payment_Advice_PAY161981.xlsx | xlsx |  | spreadsheet | PARSED | 1 | 243 |  | en | 1 | 10 |  |  |
| R01-0002 | (body) | body |  | body | PARSED |  | 175 |  | de | 0 | 0 |  |  |
| R01-0002 | Zahlungsavis_RA-2026-4999.pdf | pdf |  | text | PARSED | 1 | 716 |  | de | 0 | 44 |  |  |
| R01-0003 | (body) | body |  | body | PARSED |  | 95 |  | en | 0 | 0 |  |  |
| R01-0003 | PaymentNotice_PAY801133_scan.pdf | pdf |  | ocr | PARSED | 1 | 329 | 93.2 | en | 2 | 3259 |  | OCR pages: 1 (scanned) |
| R01-0004 | (body) | body |  | body | PARSED |  | 80 |  | en | 0 | 0 |  |  |
| R01-0004 | PaymentNotice_0352-472.pdf | pdf |  | text | PARSED | 1 | 931 |  | en | 0 | 49 |  |  |
| R01-0005 | (body) | body |  | body | PARSED |  | 93 |  | en | 0 | 0 |  |  |
| R01-0005 | Remittance_Advice_ZA-39201.pdf | pdf |  | text | PARSED | 1 | 914 |  | en | 0 | 54 |  |  |
| R01-0006 | (body) | body |  | body | PARSED |  | 85 |  | en | 0 | 0 |  |  |
| R01-0006 | Remittance_Advice_ZA-36125_scan.pdf | pdf |  | ocr | PARSED | 1 | 358 | 85.42 | en | 2 | 4255 |  | OCR pages: 1 (scanned) |
| R01-0007 | (body) | body |  | body | PARSED |  | 68 |  | en | 0 | 0 |  |  |
| R01-0007 | PaymentNotice_PAY441817.png | image |  | ocr | PARSED | 1 | 250 | 94.97 | en | 2 | 3410 |  |  |
| R01-0008 | (body) | body |  | body | PARSED |  | 162 |  | de | 0 | 0 |  |  |
| R01-0008 | Zahlungsavis_Kunde_PAY305253.pdf | pdf |  | text | PARSED | 1 | 801 |  | de | 0 | 33 |  |  |
| R01-0009 | (body) | body |  | body | PARSED |  | 86 |  | en | 0 | 0 |  |  |
| R01-0009 | RA_RA-2026-1275.jpg | image |  | ocr | PARSED | 1 | 409 | 84.92 | en | 2 | 2167 |  |  |
| R01-0010 | (body) | body |  | body | PARSED |  | 156 |  | de | 0 | 0 |  |  |
| R01-0010 | Avis_PAY147434.pdf | pdf |  | text | PARSED | 1 | 948 |  | de | 0 | 31 |  |  |
| R01-0011 | (body) | body |  | body | PARSED |  | 173 |  | de | 0 | 0 |  |  |
| R01-0011 | Zahlungsavis_PAY256723.jpg | image |  | ocr | PARSED | 1 | 349 | 93.03 | de | 2 | 1588 |  |  |
| R01-0012 | (body) | body | yes | body | PARSED |  | 283 |  | de | 1 | 0 |  |  |
| R01-0013 | (body) | body |  | body | PARSED |  | 170 |  | ja | 0 | 0 |  |  |
| R01-0013 | Payment_Notice_ZA-30849.pdf | pdf |  | text | PARSED | 1 | 653 |  | en | 0 | 39 |  |  |
| R01-0014 | (body) | body |  | body | PARSED |  | 66 |  | en | 0 | 0 |  |  |
| R01-0014 | PaymentNotice_PAY378636.pdf | pdf |  | text | PARSED | 1 | 755 |  | en | 0 | 37 |  |  |
| R01-0015 | (body) | body |  | body | PARSED |  | 159 |  | ja | 0 | 0 |  |  |
| R01-0015 | Payment_Notice_ZA-37246.docx | docx |  | docx | PARSED |  | 338 |  | ja | 1 | 28 |  |  |
| R01-0016 | (body) | body |  | body | PARSED |  | 87 |  | en | 0 | 0 |  |  |
| R01-0016 | Remittance_Advice_RA-2026-4538.docx | docx |  | docx | PARSED |  | 511 |  | en | 1 | 16 |  |  |
| R01-0017 | (body) | body |  | body | PARSED |  | 78 |  | en | 0 | 0 |  |  |
| R01-0017 | RA_PAY776861.docx | docx |  | docx | PARSED |  | 550 |  | en | 1 | 21 |  |  |
| R01-0018 | (body) | body |  | body | PARSED |  | 88 |  | en | 0 | 0 |  |  |
| R01-0018 | RA_PV7211227.pdf | pdf |  | text | PARSED | 1 | 848 |  | en | 0 | 33 |  |  |
| R02-0019 | (body) | body | yes | body | PARSED |  | 247 |  | de | 1 | 0 |  |  |
| R02-0020 | (body) | body | yes | body | PARSED |  | 149 |  | en | 1 | 0 |  |  |
| R02-0021 | (body) | body | yes | body | PARSED |  | 137 |  | en | 1 | 0 |  |  |
| R02-0022 | (body) | body | yes | body | PARSED |  | 178 |  | en | 1 | 0 |  |  |
| R02-0023 | (body) | body | yes | body | PARSED |  | 166 |  | fr | 1 | 0 |  |  |
| R03-0024 | (body) | body |  | body | PARSED |  | 68 |  | fr | 0 | 0 |  |  |
| R03-0024 | Avis_de_paiement_RA-2026-7040.docx | docx |  | docx | PARSED |  | 1073 |  | fr | 1 | 29 |  |  |
| R03-0025 | (body) | body |  | body | PARSED |  | 159 |  | ja | 0 | 0 |  |  |
| R03-0025 | furikomi_tsuchi_ZA-63080.jpg | image |  | ocr | PARSED | 1 | 508 | 88.06 | ja | 3 | 4548 |  |  |
| R03-0026 | (body) | body |  | body | PARSED |  | 87 |  | en | 0 | 0 |  |  |
| R03-0026 | remittance_PV9212474.pdf | pdf |  | text | PARSED | 1 | 1046 |  | en | 0 | 59 |  |  |
| R03-0027 | (body) | body |  | body | PARSED |  | 61 |  | en | 0 | 0 |  |  |
| R03-0027 | RA_PAY266479_scan.pdf | pdf |  | ocr | PARSED | 1 | 572 | 89.39 | en | 2 | 3810 |  | OCR pages: 1 (scanned) |
| R03-0028 | (body) | body |  | body | PARSED |  | 97 |  | en | 0 | 0 |  |  |
| R03-0028 | Remittance_Advice_RA-2026-7585.pdf | pdf |  | text | PARSED | 1 | 3268 |  | en | 0 | 82 |  |  |
| R03-0029 | (body) | body |  | body | PARSED |  | 181 |  | de | 0 | 0 |  |  |
| R03-0029 | Zahlungsavis_Kunde_ZA-95921.docx | docx |  | docx | PARSED |  | 785 |  | de | 1 | 18 |  |  |
| R03-0030 | (body) | body |  | body | PARSED |  | 61 |  | en | 0 | 0 |  |  |
| R03-0030 | Payment_Advice_ZA-36628.pdf | pdf |  | text | PARSED | 1 | 2617 |  | en | 0 | 132 |  |  |
| R03-0031 | (body) | body |  | body | PARSED |  | 136 |  | es | 0 | 0 |  |  |
| R03-0031 | Aviso_de_pago_RA-2026-4310.docx | docx |  | docx | PARSED |  | 691 |  | es | 1 | 28 |  |  |
| R03-0032 | (body) | body |  | body | PARSED |  | 168 |  | de | 0 | 0 |  |  |
| R03-0032 | Avis_PV9753213.pdf | pdf |  | text | PARSED | 1 | 1409 |  | de | 0 | 39 |  |  |
| R03-0033 | (body) | body |  | body | PARSED |  | 165 |  | de | 0 | 0 |  |  |
| R03-0033 | Zahlungsavis_Kunde_PAY827123.pdf | pdf |  | text | PARSED | 1 | 1610 |  | de | 0 | 43 |  |  |
| R03-0034 | (body) | body |  | body | PARSED |  | 175 |  | de | 0 | 0 |  |  |
| R03-0034 | Avis_PAY268655_scan.pdf | pdf |  | ocr | PARSED | 1 | 546 | 90.72 | de | 2 | 3348 |  | OCR pages: 1 (scanned) |
| R03-0035 | (body) | body |  | body | PARSED |  | 80 |  | en | 0 | 0 |  |  |
| R03-0035 | RA_PAY549307.pdf | pdf |  | text | PARSED | 1 | 2336 |  | en | 0 | 53 |  |  |
| R03-0036 | (body) | body |  | body | PARSED |  | 105 |  | en | 0 | 0 |  |  |
| R03-0036 | PaymentNotice_RA-2026-9050.png | image |  | ocr | PARSED | 1 | 706 | 93.78 | en | 2 | 3860 |  |  |
| R03-0037 | (body) | body |  | body | PARSED |  | 78 |  | en | 0 | 0 |  |  |
| R03-0037 | PaymentNotice_PAY738253_scan.pdf | pdf |  | ocr | PARSED | 1 | 844 | 71.92 | en | 6 | 5397 |  | OCR pages: 1 (scanned) |
| R04-0038 | (body) | body |  | body | PARSED |  | 66 |  | en | 0 | 0 |  |  |
| R04-0038 | Payment_Advice_PAY192420.pdf | pdf |  | text | PARSED | 1 | 960 |  | en | 0 | 36 |  |  |
| R04-0039 | (body) | body |  | body | PARSED |  | 68 |  | fr | 0 | 0 |  |  |
| R04-0039 | AvisVirement_RA-2026-3727.docx | docx |  | docx | PARSED |  | 471 |  | fr | 1 | 15 |  |  |
| R04-0040 | (body) | body |  | body | PARSED |  | 61 |  | en | 0 | 0 |  |  |
| R04-0040 | RA_PAY264920.pdf | pdf |  | text | PARSED | 1 | 869 |  | en | 0 | 37 |  |  |
| R04-0041 | (body) | body |  | body | PARSED |  | 148 |  | de | 0 | 0 |  |  |
| R04-0041 | Zahlungsavis_Kunde_1028-428.pdf | pdf |  | text | PARSED | 1 | 776 |  | de | 0 | 32 |  |  |
| R04-0042 | (body) | body |  | body | PARSED |  | 78 |  | en | 0 | 0 |  |  |
| R04-0042 | RA_RA-2026-3144.pdf | pdf |  | text | PARSED | 1 | 710 |  | en | 0 | 36 |  |  |
| R04-0043 | (body) | body |  | body | PARSED |  | 59 |  | en | 0 | 0 |  |  |
| R04-0043 | remittance_PAY977886_scan.pdf | pdf |  | ocr | PARSED | 1 | 286 | 94.1 | en | 2 | 3302 |  | OCR pages: 1 (scanned) |
| R04-0044 | (body) | body |  | body | PARSED |  | 88 |  | en | 0 | 0 |  |  |
| R04-0044 | Remittance_Advice_PV1426477.jpg | image |  | ocr | PARSED | 1 | 372 | 87.48 | en | 2 | 2463 |  |  |
| R04-0045 | (body) | body |  | body | PARSED |  | 148 |  | de | 0 | 0 |  |  |
| R04-0045 | Zahlungsavis_Kunde_1028-962.pdf | pdf |  | text | PARSED | 1 | 732 |  | de | 0 | 41 |  |  |
| R05-0046 | (body) | body |  | body | PARSED |  | 143 |  | es | 0 | 0 |  |  |
| R05-0046 | Aviso_de_pago_ZA-21611.pdf | pdf |  | text | PARSED | 1 | 611 |  | es | 0 | 43 |  |  |
| R05-0047 | (body) | body | yes | body | PARSED |  | 338 |  | ja | 1 | 0 |  |  |
| R05-0048 | (body) | body | yes | body | PARSED |  | 185 |  | en | 1 | 0 |  |  |
| R05-0049 | (body) | body |  | body | PARSED |  | 66 |  | en | 0 | 0 |  |  |
| R05-0049 | remittance_PAY407861.jpg | image |  | ocr | PARSED | 1 | 350 | 93.19 | en | 2 | 3340 |  |  |
| R05-0050 | (body) | body |  | body | PARSED |  | 66 |  | en | 0 | 0 |  |  |
| R05-0050 | RA_PAY874652.pdf | pdf |  | text | PARSED | 1 | 938 |  | en | 0 | 39 |  |  |
| R05-0051 | (body) | body |  | body | PARSED |  | 105 |  | en | 0 | 0 |  |  |
| R05-0051 | Remittance_Advice_PAY149746.xlsx | xlsx |  | spreadsheet | PARSED | 1 | 359 |  | en | 1 | 10 |  |  |
| R05-0052 | (body) | body | yes | body | PARSED |  | 192 |  | en | 1 | 0 |  |  |
| R06-0053 | (body) | body |  | body | PARSED |  | 78 |  | en | 0 | 0 |  |  |
| R06-0053 | Remittance_Advice_PV1259058.pdf | pdf |  | text | PARSED | 1 | 778 |  | en | 0 | 50 |  |  |
| R06-0054 | (body) | body |  | body | PARSED |  | 166 |  | de | 0 | 0 |  |  |
| R06-0054 | Zahlungsavis_Kunde_PV2057342.pdf | pdf |  | text | PARSED | 1 | 1006 |  | de | 0 | 35 |  |  |
| R06-0055 | (body) | body | yes | body | PARSED |  | 205 |  | en | 1 | 0 |  |  |
| R06-0056 | (body) | body |  | body | PARSED |  | 61 |  | en | 0 | 0 |  |  |
| R06-0056 | RA_ZA-26750.docx | docx |  | docx | PARSED |  | 515 |  | en | 1 | 19 |  |  |
| R07-0057 | (body) | body |  | body | PARSED |  | 169 |  | ja | 0 | 0 |  |  |
| R07-0057 | Payment_Notice_2263-835.pdf | pdf |  | text | PARSED | 1 | 697 |  | ja | 0 | 51 |  |  |
| R07-0058 | (body) | body |  | body | PARSED |  | 117 |  | en | 0 | 0 |  |  |
| R07-0058 | remittance_PAY759373.csv | csv |  | csv | PARSED |  | 153 |  | en | 1 | 5 |  |  |
| R07-0059 | (body) | body |  | body | PARSED |  | 105 |  | en | 0 | 0 |  |  |
| R07-0059 | Remittance_Advice_ZA-99269.pdf | pdf |  | text | PARSED | 1 | 853 |  | en | 0 | 34 |  |  |
| R07-0060 | (body) | body |  | body | PARSED |  | 169 |  | ja | 0 | 0 |  |  |
| R07-0060 | furikomi_tsuchi_2263-466.pdf | pdf |  | text | PARSED | 1 | 869 |  | en | 0 | 42 |  |  |
| R07-0061 | (body) | body |  | body | PARSED |  | 165 |  | de | 0 | 0 |  |  |
| R07-0061 | Zahlungsavis_ZA-17907.jpg | image |  | ocr | PARSED | 1 | 361 | 93.89 | de | 2 | 3191 |  |  |
| R07-0062 | (body) | body | yes | body | PARSED |  | 313 |  | de | 1 | 0 |  |  |
| R07-0063 | (body) | body |  | body | PARSED |  | 191 |  | de | 0 | 0 |  |  |
| R07-0063 | Zahlungsavis_Kunde_ZA-11153.pdf | pdf |  | text | PARSED | 1 | 979 |  | de | 0 | 39 |  |  |
| R08-0064 | (body) | body |  | body | PARSED |  | 68 |  | fr | 0 | 0 |  |  |
| R08-0064 | AvisVirement_RA-2026-6626_scan.pdf | pdf |  | ocr | PARSED | 1 | 394 | 92.52 | fr | 2 | 3053 |  | OCR pages: 1 (scanned) |
| R08-0065 | (body) | body |  | body | PARSED |  | 78 |  | en | 0 | 0 |  |  |
| R08-0065 | remittance_PAY490434.pdf | pdf |  | text | PARSED | 1 | 866 |  | en | 0 | 40 |  |  |
| R08-0066 | (body) | body |  | body | PARSED |  | 86 |  | en | 0 | 0 |  |  |
| R08-0066 | Payment_Advice_ZA-41778.pdf | pdf |  | text | PARSED | 1 | 757 |  | en | 0 | 37 |  |  |
| R08-0067 | (body) | body |  | body | PARSED |  | 61 |  | en | 0 | 0 |  |  |
| R08-0067 | RA_PV8526043.png | image |  | ocr | PARSED | 1 | 401 | 94.4 | en | 2 | 3330 |  |  |
| R08-0068 | (body) | body |  | body | PARSED |  | 133 |  | de | 0 | 0 |  |  |
| R08-0068 | Zahlungsavis_1028-351_scan.pdf | pdf |  | ocr | PARSED | 1 | 299 | 93.97 | de | 2 | 3037 |  | OCR pages: 1 (scanned) |
| R08-0069 | (body) | body |  | body | PARSED |  | 68 |  | en | 0 | 0 |  |  |
| R08-0069 | remittance_PAY310079.pdf | pdf |  | text | PARSED | 1 | 862 |  | en | 0 | 36 |  |  |
| R09-0070 | (body) | body |  | body | PARSED |  | 78 |  | en | 0 | 0 |  |  |
| R09-0070 | Payment_Advice_PAY369502.pdf | pdf |  | text | PARSED | 1 | 968 |  | en | 0 | 51 |  |  |
| R09-0071 | (body) | body |  | body | PARSED |  | 59 |  | en | 0 | 0 |  |  |
| R09-0071 | remittance_PAY257908.pdf | pdf |  | text | PARSED | 1 | 924 |  | en | 0 | 44 |  |  |
| R09-0072 | (body) | body |  | body | PARSED |  | 154 |  | de | 0 | 0 |  |  |
| R09-0072 | Zahlungsavis_Kunde_ZA-43020.pdf | pdf |  | text | PARSED | 1 | 1060 |  | de | 0 | 60 |  |  |
| R09-0073 | (body) | body |  | body | PARSED |  | 175 |  | de | 0 | 0 |  |  |
| R09-0073 | Avis_ZA-24622.pdf | pdf |  | text | PARSED | 1 | 972 |  | de | 0 | 33 |  |  |
| R09-0074 | (body) | body |  | body | PARSED |  | 87 |  | en | 0 | 0 |  |  |
| R09-0074 | remittance_ZA-24727.jpg | image |  | ocr | PARSED | 1 | 441 | 94.21 | en | 2 | 1932 |  |  |
| R09-0075 | (body) | body |  | body | PARSED |  | 163 |  | de | 0 | 0 |  |  |
| R09-0075 | Avis_PAY498346.pdf | pdf |  | text | PARSED | 1 | 931 |  | de | 0 | 36 |  |  |
| R10-0076 | (body) | body |  | body | PARSED |  | 68 |  | fr | 0 | 0 |  |  |
| R10-0076 | AvisVirement_RA-2026-6927.pdf | pdf |  | text | PARSED | 1 | 1058 |  | fr | 0 | 37 |  |  |
| R10-0077 | (body) | body |  | body | PARSED |  | 68 |  | fr | 0 | 0 |  |  |
| R10-0077 | AvisVirement_PAY421430.pdf | pdf |  | text | PARSED | 1 | 1153 |  | fr | 0 | 56 |  |  |
| R10-0078 | (body) | body |  | body | PARSED |  | 159 |  | de | 0 | 0 |  |  |
| R10-0078 | Avis_ZA-64357.pdf | pdf |  | text | PARSED | 1 | 792 |  | de | 0 | 45 |  |  |
| R10-0079 | (body) | body |  | body | PARSED |  | 61 |  | en | 0 | 0 |  |  |
| R10-0079 | remittance_PAY677112.xlsx | xlsx |  | spreadsheet | PARSED | 1 | 264 |  | en | 1 | 8 |  |  |
| R10-0080 | (body) | body |  | body | PARSED |  | 61 |  | en | 0 | 0 |  |  |
| R10-0080 | Payment_Advice_0380-108.xlsx | xlsx |  | spreadsheet | PARSED | 1 | 472 |  | en | 1 | 10 |  |  |
| R10-0081 | (body) | body |  | body | PARSED |  | 85 |  | en | 0 | 0 |  |  |
| R10-0081 | Remittance_Advice_ZA-37119.pdf | pdf |  | text | PARSED | 1 | 1126 |  | en | 0 | 48 |  |  |
| R11-0082 | (body) | body |  | body | PARSED |  | 59 |  | en | 0 | 0 |  |  |
| R11-0082 | RA_PAY827913.pdf | pdf |  | text | PARSED | 1 | 894 |  | en | 0 | 33 |  |  |
| R11-0083 | (body) | body |  | body | PARSED |  | 88 |  | en | 0 | 0 |  |  |
| R11-0083 | Remittance_Advice_RA-2026-4184.pdf | pdf |  | text | PARSED | 1 | 731 |  | en | 0 | 152 |  |  |
| R11-0084 | (body) | body |  | body | PARSED |  | 86 |  | en | 0 | 0 |  |  |
| R11-0084 | PaymentNotice_PAY447740.pdf | pdf |  | text | PARSED | 1 | 875 |  | en | 0 | 34 |  |  |
| R11-0085 | (body) | body |  | body | PARSED |  | 154 |  | de | 0 | 0 |  |  |
| R11-0085 | Zahlungsavis_PAY132422.xlsx | xlsx |  | spreadsheet | PARSED | 1 | 136 |  | de | 1 | 8 |  |  |
| R12-0086 | (body) | body | yes | body | PARSED |  | 163 |  | de | 0 | 0 |  |  |
| R12-0087 | (body) | body | yes | body | PARSED |  | 111 |  | en | 0 | 0 |  |  |
| R12-0088 | (body) | body | yes | body | PARSED |  | 111 |  | en | 0 | 0 |  |  |
| R12-0089 | (body) | body | yes | body | PARSED |  | 81 |  | ja | 0 | 0 |  |  |
| R12-0090 | (body) | body | yes | body | PARSED |  | 158 |  | de | 0 | 0 |  |  |
| R13-0091 | (body) | body | yes | body | PARSED |  | 222 |  | de | 0 | 0 |  |  |
| R13-0092 | (body) | body |  | body | PARSED |  | 88 |  | en | 0 | 0 |  |  |
| R13-0092 | Remittance_Advice_PAY530761.docx | docx |  | docx | PARSED |  | 417 |  | en | 0 | 15 |  |  |
| R13-0093 | (body) | body |  | body | PARSED |  | 59 |  | fr | 0 | 0 |  |  |
| R13-0093 | Avis_de_paiement_PAY955482.docx | docx |  | docx | PARSED |  | 422 |  | fr | 0 | 21 |  |  |
| R13-0094 | (body) | body |  | body | PARSED |  | 66 |  | en | 0 | 0 |  |  |
| R13-0094 | PaymentNotice_PV7305937.docx | docx |  | docx | PARSED |  | 430 |  | en | 0 | 14 |  |  |
| R14-0095 | (body) | body |  | body | PARSED |  | 85 |  | en | 0 | 0 |  |  |
| R14-0095 | RA_ZA-65142.docx | docx |  | docx | PARSED |  | 518 |  | en | 1 | 17 |  |  |
| R14-0096 | (body) | body |  | body | PARSED |  | 152 |  | de | 0 | 0 |  |  |
| R14-0096 | Zahlungsavis_Kunde_ZA-91358.pdf | pdf |  | text | PARSED | 1 | 763 |  | de | 0 | 45 |  |  |
| R14-0097 | (body) | body | yes | body | PARSED |  | 248 |  | ja | 1 | 0 |  |  |
| R14-0098 | (body) | body |  | body | PARSED |  | 176 |  | de | 0 | 0 |  |  |
| R14-0098 | Zahlungsavis_PAY103258.pdf | pdf |  | text | PARSED | 1 | 797 |  | de | 0 | 46 |  |  |
| R16-0099 | (body) | body |  | body | PARSED |  | 59 |  | fr | 0 | 0 |  |  |
| R16-0099 | AvisVirement_RA-2026-9474.docx | docx |  | docx | PARSED |  | 527 |  | fr | 1 | 17 |  |  |
| R16-0100 | (body) | body |  | body | PARSED |  | 78 |  | en | 0 | 0 |  |  |
| R16-0100 | Payment_Advice_ZA-61158.png | image |  | ocr | PARSED | 1 | 315 | 87.16 | en | 2 | 2405 |  |  |
| R16-0101 | (body) | body |  | body | PARSED |  | 105 |  | en | 0 | 0 |  |  |
| R16-0101 | remittance_PAY609629.png | image |  | ocr | PARSED | 1 | 311 | 94.53 | en | 2 | 3524 |  |  |
| R16-0102 | (body) | body |  | body | PARSED |  | 78 |  | en | 0 | 0 |  |  |
| R16-0102 | Remittance_Advice_2077-982.docx | docx |  | docx | PARSED |  | 520 |  | en | 1 | 19 |  |  |
| R16-0103 | (body) | body |  | body | PARSED |  | 78 |  | en | 0 | 0 |  |  |
| R16-0103 | RA_0970-291.pdf | pdf |  | text | PARSED | 1 | 771 |  | en | 0 | 50 |  |  |
| R17-0104 | (body) | body |  | body | PARSED |  | 154 |  | de | 0 | 0 |  |  |
| R17-0104 | Avis_PAY804359.pdf | pdf |  | text | PARSED | 1 | 646 |  | de | 0 | 37 |  |  |
| R17-0105 | (body) | body | yes | body | PARSED |  | 193 |  | en | 1 | 0 |  |  |
| R17-0106 | (body) | body |  | body | PARSED |  | 86 |  | en | 0 | 0 |  |  |
| R17-0106 | Remittance_Advice_0380-101.png | image |  | ocr | PARSED | 1 | 316 | 76.02 | en | 2 | 4961 |  |  |
| R17-0107 | (body) | body |  | body | PARSED |  | 146 |  | de | 0 | 0 |  |  |
| R17-0107 | Avis_PV7064979.xlsx | xlsx |  | spreadsheet | PARSED | 1 | 222 |  | de | 1 | 7 |  |  |
| R18-0108 | (body) | body |  | body | PARSED |  | 193 |  | de | 0 | 0 |  |  |
| R18-0108 | Zahlungsavis_ZA-21729.pdf | pdf |  | text | PARSED | 1 | 920 |  | de | 0 | 38 |  |  |
| R18-0109 | (body) | body |  | body | PARSED |  | 165 |  | ja | 0 | 0 |  |  |
| R18-0109 | Payment_Notice_PV7445475.pdf | pdf |  | text | PARSED | 1 | 786 |  | sw | 0 | 41 |  |  |
| R18-0110 | (body) | body |  | body | PARSED |  | 59 |  | en | 0 | 0 |  |  |
| R18-0110 | remittance_PAY174990.xlsx | xlsx |  | spreadsheet | PARSED | 1 | 142 |  | en | 1 | 9 |  |  |
| R18-0111 | (body) | body |  | body | PARSED |  | 78 |  | en | 0 | 0 |  |  |
| R18-0111 | remittance_ZA-92253_scan.pdf | pdf |  | ocr | PARSED | 1 | 298 | 91.61 | en | 2 | 3595 |  | OCR pages: 1 (scanned) |
| R19-0112 | (body) | body |  | body | PARSED |  | 95 |  | en | 0 | 0 |  |  |
| R19-0112 | Payment_Advice_2469-258.docx | docx |  | docx | PARSED |  | 502 |  | en | 1 | 16 |  |  |
| R19-0113 | (body) | body |  | body | PARSED |  | 142 |  | de | 0 | 0 |  |  |
| R19-0113 | Zahlungsavis_PV7322448.jpg | image |  | ocr | PARSED | 1 | 294 | 87.1 | de | 2 | 1791 |  |  |
| R19-0114 | (body) | body |  | body | PARSED |  | 68 |  | en | 0 | 0 |  |  |
| R19-0114 | Payment_Advice_PAY472958.png | image |  | ocr | PARSED | 1 | 361 | 91.19 | en | 2 | 4486 |  |  |
| R19-0115 | (body) | body |  | body | PARSED |  | 59 |  | fr | 0 | 0 |  |  |
| R19-0115 | AvisVirement_RA-2026-2497.tif | image |  | ocr | PARSED | 1 | 332 | 79.84 | fr | 2 | 3096 |  |  |
| R19-0116 | (body) | body |  | body | PARSED |  | 66 |  | en | 0 | 0 |  |  |
| R19-0116 | RA_RA-2026-2460.pdf | pdf |  | text | PARSED | 1 | 951 |  | en | 0 | 37 |  |  |
| R20-0117 | (body) | body |  | body | PARSED |  | 95 |  | en | 0 | 0 |  |  |
| R20-0117 | Remittance_Advice_PAY139192.pdf | pdf |  | text | PARSED | 1 | 874 |  | en | 0 | 45 |  |  |
| R20-0118 | (body) | body |  | body | PARSED |  | 130 |  | en | 0 | 0 |  |  |
| R20-0118 | remittance_PAY595734.pdf | pdf |  | text | PARSED | 1 | 1043 |  | en | 0 | 48 |  |  |
| R20-0119 | (body) | body |  | body | PARSED |  | 201 |  | de | 0 | 0 |  |  |
| R20-0119 | Zahlungsavis_Kunde_PV6059478.pdf | pdf |  | text | PARSED | 1 | 914 |  | de | 0 | 35 |  |  |
| R20-0120 | (body) | body |  | body | PARSED |  | 179 |  | de | 0 | 0 |  |  |
| R20-0120 | Avis_PV2684390.xlsx | xlsx |  | spreadsheet | PARSED | 1 | 273 |  | de | 1 | 6 |  |  |
| R21-0121 | (body) | body |  | body | PARSED |  | 78 |  | en | 0 | 0 |  |  |
| R21-0121 | RA_PV1585277.tif | image |  | ocr | PARSED | 1 | 353 | 85.6 | en | 2 | 2573 |  |  |
| R21-0122 | (body) | body |  | body | PARSED |  | 87 |  | en | 0 | 0 |  |  |
| R21-0122 | remittance_PAY544439.jpg | image |  | ocr | PARSED | 1 | 314 | 89.59 | en | 2 | 1764 |  |  |
| R21-0123 | (body) | body |  | body | PARSED |  | 86 |  | en | 0 | 0 |  |  |
| R21-0123 | remittance_ZA-75558.tif | image |  | ocr | PARSED | 1 | 379 | 82.47 | en | 3 | 2987 |  |  |
| R21-0124 | (body) | body |  | body | PARSED |  | 68 |  | fr | 0 | 0 |  |  |
| R21-0124 | Avis_de_paiement_RA-2026-5269.png | image |  | ocr | PARSED | 1 | 486 | 87.27 | fr | 2 | 2126 |  |  |
| R21-0125 | (body) | body |  | body | PARSED |  | 66 |  | en | 0 | 0 |  |  |
| R21-0125 | Payment_Advice_PAY567172.png | image |  | ocr | PARSED | 1 | 279 | 88.76 | en | 2 | 1808 |  |  |
| R21-0126 | (body) | body |  | body | PARSED |  | 78 |  | en | 0 | 0 |  |  |
| R21-0126 | PaymentNotice_ZA-89448.jpg | image |  | ocr | PARSED | 1 | 436 | 91.8 | en | 2 | 1914 |  |  |
| R21-0127 | (body) | body |  | body | PARSED |  | 68 |  | en | 0 | 0 |  |  |
| R21-0127 | RA_2077-585.png | image |  | ocr | PARSED | 1 | 341 | 89.87 | en | 2 | 1792 |  |  |
| R22-0128 | (body) | body | yes | body | PARSED |  | 268 |  | en | 1 | 0 |  |  |
| R22-0129 | (body) | body | yes | body | PARSED |  | 281 |  | de | 1 | 0 |  |  |
| R22-0130 | (body) | body | yes | body | PARSED |  | 310 |  | ja | 1 | 0 |  |  |
| R22-0131 | (body) | body | yes | body | PARSED |  | 272 |  | de | 1 | 0 |  |  |
| R22-0132 | (body) | body | yes | body | PARSED |  | 292 |  | en | 1 | 0 |  |  |
| R22-0133 | (body) | body | yes | body | PARSED |  | 192 |  | en | 1 | 0 |  |  |
| R23-0134 | (body) | body |  | body | PARSED |  | 85 |  | en | 0 | 0 |  |  |
| R23-0134 | RA_PV7152545.pdf | pdf |  | text | PARSED | 1 | 956 |  | en | 0 | 36 |  |  |
| R23-0134 | RA_PV8415384_detail.xlsx | xlsx |  | spreadsheet | PARSED | 1 | 237 |  | en | 1 | 8 |  |  |
| R23-0135 | (body) | body |  | body | PARSED |  | 162 |  | ja | 0 | 0 |  |  |
| R23-0135 | furikomi_tsuchi_ZA-59151.pdf | pdf |  | text | PARSED | 1 | 1067 |  | et | 0 | 38 |  |  |
| R23-0135 | furikomi_tsuchi_ZA-81881_detail.xlsx | xlsx |  | spreadsheet | PARSED | 1 | 251 |  | en | 1 | 20 |  |  |
| R23-0136 | (body) | body |  | body | PARSED |  | 128 |  | de | 0 | 0 |  |  |
| R23-0136 | Zahlungsavis_1028-162.pdf | pdf |  | text | PARSED | 1 | 1146 |  | de | 0 | 40 |  |  |
| R23-0136 | Zahlungsavis_Kunde_1028-135_detail.xlsx | xlsx |  | spreadsheet | PARSED | 1 | 322 |  | de | 1 | 6 |  |  |
| R24-0137 | (body) | body |  | body | PARSED |  | 107 |  | en | 0 | 0 |  |  |
| R24-0137 | RA_PAY776861.docx | docx |  | docx | PARSED |  | 550 |  | en | 1 | 21 | yes |  |
| R24-0138 | (body) | body |  | body | PARSED |  | 152 |  | de | 0 | 0 |  |  |
| R24-0138 | Zahlungsavis_1028-351_scan.pdf | pdf |  | ocr | PARSED | 1 | 299 | 93.97 | de | 2 | 3037 | yes | OCR pages: 1 (scanned) |
| R24-0139 | (body) | body |  | body | PARSED |  | 165 |  | es | 0 | 0 |  |  |
| R24-0139 | Aviso_de_pago_RA-2026-4310.docx | docx |  | docx | PARSED |  | 691 |  | es | 1 | 28 | yes |  |
| R24-0140 | (body) | body |  | body | PARSED |  | 134 |  | en | 0 | 0 |  |  |
| R24-0140 | PaymentNotice_RA-2026-9050.png | image |  | ocr | PARSED | 1 | 706 | 93.78 | en | 2 | 3860 | yes |  |
| R24-0141 | (body) | body |  | body | PARSED |  | 107 |  | en | 0 | 0 |  |  |
| R24-0141 | RA_PV8526043.png | image |  | ocr | PARSED | 1 | 401 | 94.4 | en | 2 | 3330 | yes |  |
| R24-0142 | (body) | body |  | body | PARSED |  | 194 |  | de | 0 | 0 |  |  |
| R24-0142 | Zahlungsavis_Kunde_PAY827123.pdf | pdf |  | text | PARSED | 1 | 1610 |  | de | 0 | 43 | yes |  |
| R25-0143 | (body) | body |  | body | PARSED |  | 86 |  | en | 0 | 0 |  |  |
| R25-0143 | remittance_PV3839148.pdf | pdf |  | text | PARSED | 1 | 962 |  | en | 0 | 38 |  |  |
| R25-0144 | (body) | body |  | body | PARSED |  | 119 |  | en | 0 | 0 |  |  |
| R25-0144 | Remittance_Advice_PV9917592.pdf | pdf |  | text | PARSED | 1 | 1022 |  | en | 0 | 42 |  |  |
| R25-0145 | (body) | body |  | body | PARSED |  | 68 |  | en | 0 | 0 |  |  |
| R25-0145 | Payment_Advice_ZA-73357.pdf | pdf |  | text | PARSED | 1 | 1040 |  | en | 0 | 36 |  |  |
| R25-0146 | (body) | body |  | body | PARSED |  | 139 |  | en | 0 | 0 |  |  |
| R25-0146 | remittance_ZA-21394.pdf | pdf |  | text | PARSED | 1 | 948 |  | en | 0 | 38 |  |  |
| R25-0147 | (body) | body |  | body | PARSED |  | 93 |  | en | 0 | 0 |  |  |
| R25-0147 | RA_0352-982.pdf | pdf |  | text | PARSED | 1 | 1034 |  | en | 0 | 37 |  |  |
| R25-0148 | (body) | body |  | body | PARSED |  | 146 |  | en | 0 | 0 |  |  |
| R25-0148 | remittance_0352-535.pdf | pdf |  | text | PARSED | 1 | 1021 |  | en | 0 | 42 |  |  |
| R26-0149 | (body) | body |  | body | PARSED |  | 85 |  | en | 0 | 0 |  |  |
| R26-0149 | RA_PAY298280.tif | image |  | ocr | PARSED | 1 | 358 | 81.1 | en | 2 | 2691 |  |  |
| R26-0150 | (body) | body |  | body | PARSED |  | 138 |  | de | 0 | 0 |  |  |
| R26-0150 | Avis_ZA-64206.pdf | pdf |  | text | PARSED | 1 | 852 |  | de | 0 | 37 |  |  |
| R26-0151 | (body) | body |  | body | PARSED |  | 86 |  | en | 0 | 0 |  |  |
| R26-0151 | Payment_Advice_PV2986423.pdf | pdf |  | text | PARSED | 1 | 687 |  | en | 0 | 37 |  |  |
| R26-0152 | (body) | body |  | body | PARSED |  | 143 |  | ja | 0 | 0 |  |  |
| R26-0152 | furikomi_tsuchi_PV2538460.pdf | pdf |  | text | PARSED | 1 | 785 |  | sw | 0 | 35 |  |  |
| R27-0153 | (body) | body |  | body | PARSED |  | 98 |  | en | 0 | 0 |  |  |
| R27-0153 | Remittance_Advice_PAY899876.xlsx | xlsx |  | spreadsheet | PARSED | 1 | 261 |  | en | 1 | 11 |  |  |
| R27-0154 | (body) | body |  | body | PARSED |  | 84 |  | en | 0 | 0 |  |  |
| R27-0154 | Remittance_Advice_PAY954703.pdf | pdf |  | text | PARSED | 1 | 887 |  | en | 0 | 39 |  |  |
| R27-0155 | (body) | body |  | body | PARSED |  | 152 |  | ja | 0 | 0 |  |  |
| R27-0155 | furikomi_tsuchi_ZA-94211.xlsx | xlsx |  | spreadsheet | PARSED | 1 | 153 |  | en | 1 | 13 |  |  |
| R27-0156 | (body) | body |  | body | PARSED |  | 123 |  | en | 0 | 0 |  |  |
| R27-0156 | PaymentNotice_ZA-70627.png | image |  | ocr | PARSED | 1 | 349 | 94.98 | en | 2 | 3403 |  |  |
| R28-0157 | (body) | body | yes | body | PARSED |  | 75 |  | en | 0 | 0 |  |  |
| R28-0158 | (body) | body | yes | body | PARSED |  | 86 |  | de | 0 | 0 |  |  |
| R28-0159 | (body) | body | yes | body | PARSED |  | 70 |  | en | 0 | 0 |  |  |
| R29-0160 | (body) | body |  | body | PARSED |  | 128 |  | en | 0 | 0 |  |  |
| R29-0160 | RA_PAY844253.pdf | pdf |  | text | PARSED | 1 | 1005 |  | en | 0 | 53 |  |  |
| R29-0161 | (body) | body |  | body | PARSED |  | 164 |  | en | 0 | 0 |  |  |
| R29-0161 | Payment_Advice_PAY915664.jpg | image |  | ocr | PARSED | 1 | 691 | 91.47 | en | 3 | 4050 |  |  |
| R29-0162 | (body) | body |  | body | PARSED |  | 164 |  | en | 0 | 0 |  |  |
| R29-0162 | PaymentNotice_PAY708600.pdf | pdf |  | text | PARSED | 1 | 837 |  | en | 0 | 50 |  |  |
| R29-0163 | (body) | body |  | body | PARSED |  | 133 |  | en | 0 | 0 |  |  |
| R29-0163 | RA_PV4940182.docx | docx |  | docx | PARSED |  | 650 |  | en | 1 | 17 |  |  |
| R29-0164 | (body) | body |  | body | PARSED |  | 145 |  | en | 0 | 0 |  |  |
| R29-0164 | Payment_Advice_PAY462880.docx | docx |  | docx | PARSED |  | 883 |  | en | 1 | 19 |  |  |
| R30-0165 | (body) | body |  | body | PARSED |  | 78 |  | en | 0 | 0 |  |  |
| R30-0165 | PaymentNotice_PAY101049.zip | container |  | container | SKIPPED |  | 0 |  |  | 0 | 0 |  | archive - its files are separate attachments |
| R30-0166 | (body) | body |  | body | PARSED |  | 138 |  | de | 0 | 0 |  |  |
| R30-0166 | Avis_ZA-55744.pdf | pdf |  | text | PARSED | 1 | 985 |  | de | 0 | 48 |  |  |
| R30-0166 | Avis_ZA-55744_lines.xlsx | xlsx |  | spreadsheet | PARSED | 1 | 222 |  | de | 1 | 7 |  |  |
| R30-0167 | (body) | body |  | body | PARSED |  | 85 |  | en | 0 | 0 |  |  |
| R30-0167 | Payment_Advice_ZA-91593.pdf | pdf |  | text | PARSED | 1 | 885 |  | en | 0 | 38 |  |  |
| R30-0167 | Payment_Advice_ZA-91593_lines.xlsx | xlsx |  | spreadsheet | PARSED | 1 | 242 |  | en | 1 | 12 |  |  |
| R31-0168 | (body) | body |  | body | PARSED |  | 78 |  | en | 0 | 0 |  |  |
| R31-0168 | Payment_Advice_0380-939.jpg | image |  | ocr | PARSED | 1 | 410 | 91.72 | en | 2 | 1753 |  |  |
| R31-0169 | (body) | body |  | body | PARSED |  | 162 |  | ja | 0 | 0 |  |  |
| R31-0169 | Payment_Notice_PV3085792.docx | docx |  | docx | PARSED |  | 363 |  | sw | 1 | 21 |  |  |
| R31-0170 | (body) | body |  | body | PARSED |  | 165 |  | ja | 0 | 0 |  |  |
| R31-0170 | furikomi_tsuchi_PV7237533.pdf | pdf |  | text | PARSED | 1 | 736 |  | sw | 0 | 40 |  |  |
| R31-0171 | (body) | body |  | body | PARSED |  | 61 |  | en | 0 | 0 |  |  |
| R31-0171 | Payment_Advice_ZA-80141.pdf | pdf |  | text | PARSED | 1 | 876 |  | en | 0 | 41 |  |  |
| R31-0172 | (body) | body |  | body | PARSED |  | 175 |  | de | 0 | 0 |  |  |
| R31-0172 | Zahlungsavis_Kunde_RA-2026-6061.pdf | pdf |  | text | PARSED | 1 | 929 |  | de | 0 | 38 |  |  |
| R32-0173 | (body) | body |  | body | PARSED |  | 78 |  | en | 0 | 0 |  |  |
| R32-0173 | Remittance_Advice_ZA-27136.pdf | pdf |  | text | PARSED | 1 | 577 |  | en | 0 | 37 |  |  |
| R32-0174 | (body) | body |  | body | PARSED |  | 159 |  | ja | 0 | 0 |  |  |
| R32-0174 | furikomi_tsuchi_ZA-36252.pdf | pdf |  | text | PARSED | 1 | 640 |  | en | 0 | 34 |  |  |
| R32-0175 | (body) | body |  | body | PARSED |  | 78 |  | en | 0 | 0 |  |  |
| R32-0175 | remittance_2469-785.pdf | pdf |  | text | PARSED | 1 | 562 |  | en | 0 | 37 |  |  |
| R32-0176 | (body) | body |  | body | PARSED |  | 59 |  | fr | 0 | 0 |  |  |
| R32-0176 | AvisVirement_PAY630622.pdf | pdf |  | text | PARSED | 1 | 582 |  | en | 0 | 38 |  |  |
| R32-0177 | (body) | body |  | body | PARSED |  | 159 |  | ja | 0 | 0 |  |  |
| R32-0177 | furikomi_tsuchi_ZA-63472.pdf | pdf |  | text | PARSED | 1 | 611 |  | en | 0 | 34 |  |  |
