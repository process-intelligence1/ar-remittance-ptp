# Presenter runbook

A 15-minute walk through the AR Remittance & PTP application. Everything shown is synthetic demo data.

## 1. The two links
| Edition | Link | What it is | Until when |
|---|---|---|---|
| **Demo edition** (permanent) | https://process-intelligence1.github.io/ar-remittance-ptp/ | Saved data in the browser, no server. 504 records (history over 3 months + 47 open ones to work on). Changes reset on reload (Reset button in the top banner). E-mails are previews, nothing is sent. | Stays online as long as the repository does. Works on any computer. |
| **Live edition** | https://process-intelligence1.github.io/ar-remittance-ptp/live/ | The real system on Azure: Gmail inbox, worker, database. Send a sample e-mail and watch it arrive. | While the free Azure account runs (about **25 Nov 2026**; never upgrade it). Afterwards `/live/` says the live system has ended and links to the demo edition. |

Access code (live edition only): the secret `demo-access-code` in the demo Key Vault. Read it in your own terminal, never in a shared screen: `az keyvault secret show --vault-name <vault name from the Azure portal> --name demo-access-code --query value -o tsv`. The demo edition needs no code.

## 2. Ten minutes before (live edition)
1. Open the live link. The first call after a quiet period shows "Starting the server... up to 1 minute" - let it finish.
2. Sign in as **Asha (AR Analyst)**.
3. **Demo Control**: the page shows "Business date 28 Oct 2026" and a reset point. Press **Reset demo** and confirm. (Check the date is 28 Oct afterwards.)
4. Have the demo mailbox open in another tab (processintelligence1@gmail.com): clarification and alert e-mails arrive there.
5. Optional rehearsal: send **R09-0070** and see it in the Action Queue after about a minute; then Reset again.

## 3. The walk-through (live edition)
| Min | Screen | Do | Say |
|---|---|---|---|
| 1 | **Dashboard** | Point at the cards and charts. | "Three months of history: about two thirds of the rows were processed automatically, the rest went to people with a reason." Counts follow the *decision*, not the status, so working a record does not move it between Auto / Manual / Exception. |
| 2 | **Demo Control** | Send **R09-0070** (a PDF payment advice with two invoices). | "A customer e-mail arrives in the inbox; the worker reads it (OCR where needed), classifies it, extracts the invoice lines and matches them to open SAP items." |
| 3 | **Action Queue** → open the new record | Show the PDF with the highlighted values (invoice numbers and amounts), the SAP BSID match, the confidence breakdown (fast path 92 %), the AI explanation and the audit timeline. Click **Confirm & Add to Excel**. | "No SAP change: the record becomes Confirmed and goes to the posting file." Then open **Exported cases (n)**: the Excel view with the new row; **Download .xlsx**. |
| 2 | **Exception** | Send **R04-0038** (invoice numbers that do not exist). It arrives as *Exception - No BSID match found*. Open it → **Request Clarification**. | The e-mail is written in the customer's language from a template; you can edit it; it goes to the demo mailbox only, with the real recipient in the subject. Status becomes *Awaiting Customer*. Show the mail; **reply to it** from the mailbox: the case comes back to *Pending Review* (reply linking - it depends on Gmail threading, so rehearse this step once). |
| 1 | **Reasons to review** | Send **R18-0108** (payment block on the open item) or **R17-0104** (several open items carry the number), **R12-0086** (no invoice number: matched by amount). | "The system never guesses silently: each of these shows why it needs a person." |
| 1 | **Duplicate** | Send **R24-0137** → *Duplicate*, points to the original. **Close as Duplicate**. | |
| 3 | **Promise to pay** | Send **P03-0193** (Pacific Rim promises SGD 8,300 on 27 Nov). Open the **Action Queue** and filter *Classification = Promise to Pay*: its **Promise Status** is *Open*. In **Demo Control** press **+30 days** (business date 27 Nov). Send **P03R-0194** (the payment advice, no promise in its text). After processing, the **Promise Status** turns *Kept*; open the record to see the payment applied. | Story B (broken): after sending only **P03-0193**, press **+30 days** (27 Nov: still *Open*, the grace period runs to 30 Nov), then **+4 days** (1 Dec): *Broken* and an alert e-mail to Collections; then **+3 days** (4 Dec): *Escalated* and an e-mail to the AR Supervisor. Each e-mail is sent once, even if you move the date back and forth. |
| 1 | **Roles** | Sign out, sign in as **Sofia (AR Supervisor)** / **Carlos (Cash Application)**. | Different roles see different actions; an escalated record is the supervisor's only. |
| 1 | **Audit Trail** | Filter by the record's entry id. | Every step: who, when, before / after, comment. |
| 1 | **Reset demo** | Demo Control → Reset demo. | Everything back to the starting point, ready for the next audience. |

**Out of scope e-mails** (O01-0218 ...) are recognised and kept out of the Action Queue; they remain in the Audit Trail.

## 4. The walk-through (demo edition, no Gmail)
Same screens, working on the 47 open records already in the queue: pick one from the table below (for example an exception, a duplicate, a payment-block row), open it, use the actions (Confirm, Reject, Escalate, Request Clarification as a preview, Close as Duplicate), watch **Exported cases** and the **Dashboard**, then press **Reset** in the top banner. Not available there (greyed or hidden, with a note): Add / Update Invoice Details, Add BSID Invoice Details, Mark as Non-Duplicate (they match and score again, which needs the live system), Demo Control, sending samples, moving the business date, the promise re-check.

## 5. What each live sample does
Generated from the demo data (3 Nov 2026). In the live edition the result should be the same; the *Rows* column is the number of invoice rows the e-mail produces.

| Sample | Type | Customer | Rows | Result in the queue | Why |
|---|---|---|---|---|---|
| O01-0218 | Out of scope | - | 1 | 1x Out Of Scope | - |
| O02-0221 | Out of scope | - | 1 | 1x Out Of Scope | - |
| O03-0224 | Out of scope | - | 1 | 1x Out Of Scope | - |
| O04-0226 | Out of scope | - | 1 | 1x Out Of Scope | - |
| O05-0228 | Out of scope | - | 1 | 1x Out Of Scope | - |
| O06-0231 | Out of scope | - | 1 | 1x Out Of Scope | - |
| O07-0233 | Out of scope | - | 1 | 1x Out Of Scope | - |
| P01-0178 | Promise to pay | Seoul Display Materials Co., | 1 | 1x Auto Process | - |
| P02-0187 | Promise to pay | Highland Spirits Distillers  | 4 | 4x Auto Process | - |
| P03-0193 | Promise to pay | Pacific Rim Traders Pte. Ltd | 1 | 1x Auto Process | - |
| P03R-0194 | Payment after a promise | Pacific Rim Traders Pte. Ltd | 1 | 1x Auto Process | - |
| P05-0201 | Promise to pay | Paulista Agro Comercio Ltda | 2 | 2x Auto Process | - |
| P05R-0202 | Payment after a promise | Paulista Agro Comercio Ltda | 2 | 2x Auto Process | - |
| P06-0207 | Payment + promise | Shree Ganesh Textiles Pvt. L | 4 | 4x Auto Process | - |
| P07-0212 | Promise to pay | Konkan Auto Components Pvt.  | 1 | 1x Manual Review | Invoice belongs to customer 101721 (Konkan Auto Components P |
| P08-0215 | Promise to pay | Great Lakes Auto Parts Inc. | 3 | 3x Manual Review | - |
| R01-0001 | Remittance | Highland Spirits Distillers  | 1 | 1x Auto Process | - |
| R02-0019 | Remittance | Elbe Chemie GmbH | 1 | 1x Auto Process | - |
| R03-0024 | Remittance | Provence Agroalimentaire SAS | 10 | 10x Auto Process | - |
| R04-0038 | Remittance | Konkan Auto Components Pvt.  | 1 | 1x Exception | No BSID match found |
| R05-0046 | Remittance | Azteca Industrial S.A. de C. | 1 | 1x Manual Review | - |
| R06-0053 | Remittance | Techniques Avancees du Nord  | 1 | 1x Manual Review | Invoice belongs to customer 101193 (Techniques Avancees du N |
| R07-0057 | Remittance | Hokkaido Dairy Cooperative 北 | 1 | 1x Manual Review | - |
| R08-0064 | Remittance | Provence Agroalimentaire SAS | 1 | 1x Auto Process | - |
| R09-0070 | Remittance | Pacific Rim Traders Pte. Ltd | 2 | 2x Auto Process | - |
| R10-0076 | Remittance | Brasserie des Alpes SARL | 3 | 3x Auto Process | - |
| R11-0082 | Remittance | Thameside Engineering plc | 1 | 1x Auto Process | - |
| R12-0086 | Remittance | Bavaria Medizintechnik GmbH | 1 | 1x Manual Review | No invoice number - matched by amount (1 invoice(s), differe |
| R13-0091 | Remittance | Schwarzwald Feinmechanik Gmb | 2 | 2x Manual Review | No invoice number - matched by amount (2 invoice(s), differe |
| R14-0095 | Remittance | Pennine Textiles Ltd | 1 | 1x Auto Process | - |
| R16-0099 | Remittance | Brasserie des Alpes SARL | 1 | 1x Exception | No BSID match found |
| R17-0104 | Remittance | Helvetia Praezision AG | 1 | 1x Manual Review | Several open items carry this number |
| R18-0108 | Remittance | Schwarzwald Feinmechanik Gmb | 1 | 1x Manual Review | Payment block on the open item (ZLSPR = R) |
| R19-0112 | Remittance | Kangaroo Valley Wines Pty Lt | 1 | 1x Manual Review | - |
| R20-0117 | Remittance | Meridian Foods Inc. | 3 | 3x Auto Process | - |
| R21-0121 | Remittance | Al Noor Petrochemical Servic | 1 | 1x Auto Process | - |
| R22-0128 | Remittance | Pennine Textiles Ltd | 3 | 3x Auto Process | - |
| R23-0134 | Remittance | Al Noor Petrochemical Servic | 1 | 1x Auto Process | - |
| R24-0137 | Remittance | Seoul Display Materials Co., | 1 | 1x Duplicate | - |
| R25-0143 | Remittance | Shri Ganesh Textile Mills | 2 | 2x Auto Process | - |
| R26-0149 | Remittance | Konkan Auto Components Pvt.  | 1 | 1x Exception | No BSID match found |
| R27-0153 | Remittance | Shree Ganesh Textiles Pvt. L | 1 | 1x Manual Review | - |
| R28-0157 | Remittance | Gulf Star Trading LLC | 1 | 1x Manual Review | No invoice number - matched by amount (1 invoice(s), differe |
| R29-0160 | Remittance | Tamilnad Agro Exports Pvt. L | 2 | 2x Auto Process | - |
| R30-0165 | Remittance | Deccan Pharma Ltd. | 2 | 2x Auto Process | - |
| R31-0168 | Remittance | Pinnacle Aerospace Component | 1 | 1x Auto Process | - |
| R32-0173 | Remittance | Cardiff Bay Marine Services  | 1 | 1x Auto Process | - |

## 6. If something goes wrong
| You see | Do |
|---|---|
| "Starting the server..." for more than a minute, or "Retry" | Press Retry. The server sleeps when idle; the first call can take up to a minute. |
| Signed out suddenly | The session is limited (10 h token, 60 min idle). Sign in again. |
| A sample was sent but nothing appears | The worker runs every 10 minutes; use **Process now** in Demo Control, then wait about a minute. |
| "Send sample" fails with a Gmail message | The Gmail permission needs renewing: see `CLAUDE.md` ("After ANY Gmail token renewal"). Use the demo edition meanwhile. |
| Reset says a job is running | Wait a minute and try again. |
| Reset says there is no reset point | The history has not been built in this environment: run the one-off job `ar-history` (see `docs/modules/M11_demo_control.md`). |
| The live link is gone | Azure has ended or is down: use the demo edition. |

## 7. When Azure ends (about 25 Nov 2026)
1. Set the repository variable `LIVE_ENDED` to `true` (GitHub: Settings → Secrets and variables → Actions → Variables), then run the workflow "Publish site (GitHub Pages)" again: `/live/` then shows a "live system has ended" page with a link to the demo edition.
2. Optional: delete the Azure resource group `rg-ar-demo` yourself in the Azure portal (nothing else needs it). Never click Upgrade.
3. The demo edition, the repository and all documents stay as they are.
