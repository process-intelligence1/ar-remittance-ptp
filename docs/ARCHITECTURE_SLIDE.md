# Architecture - slide content

## Slide 1: How it works
**Title:** From customer e-mail to a posted payment - with a person where it matters

```
Customer e-mail (Gmail inbox)           Worker (every 10 min, or "Process now")
   + attachments  ───────────────────►  1 Read      PDF text / OCR (Tesseract), Word, Excel, images
                                        2 Classify  remittance / promise / out of scope  (rules + small model)
                                        3 Extract   invoice lines, amounts, dates, promise dates (EN DE FR ES PT JA)
                                        4 Match     to open SAP items (BSID) - invoice number first, then amount, name, date
                                        5 Decide    confidence → Auto process / Manual review / Exception / Duplicate
                                                    │
                                                    ▼
   PostgreSQL ── SAP simulated (BSID, KNA1 ...)  read-only      Workbench (React web app)
              ── work items, audit trail, jobs                   Dashboard · Action Queue · Record Detail
                                                    ◄──────────  Confirm & Add to Excel · Reject · Clarify · Escalate
   Promise-to-pay check (business date) ───────────►            Promise status in the queue · alert / escalation e-mails
```

Key points
- One row per invoice; every step leaves an audit entry (who, when, before / after).
- Rules first, a small model only when the rules are unsure; no LLM, no data leaves the system.
- Confidence = max(fast path, weighted formula): invoice match 35 %, amount 30 %, sender-to-company 10 %, name 10 %, date 5 %.
- "Confirm & Add to Excel" never changes SAP data: the record becomes Confirmed and the Excel file is the posting file.
- Every outgoing e-mail goes to the demo mailbox only, with the real recipient in the subject.

## Slide 2: How it is run (zero cost) and how it is protected
| Layer | This demo | Why it is enough here |
|---|---|---|
| Front-end | React + Vite + TypeScript on GitHub Pages - **two editions**: demo (saved data, no server) and live | A permanent shareable demo that costs nothing and works after Azure ends |
| API + worker | Python / FastAPI on Azure Container Apps (scale to zero), worker as a scheduled job; one-off jobs for migrations and the history | Pay nothing while idle; the free grant covers the runs |
| Data | Azure PostgreSQL (B1ms), Blob storage for e-mails and attachments, Key Vault for secrets | Managed, small, no VMs or public IPs |
| Delivery | GitHub Actions + Bicep (infrastructure as code); images in the public GitHub registry | Repeatable; deploys wait for an approval |
| Safety | Demo access code + signed tokens, least-privilege identities, secret scanning on every push, e-mail redirect, synthetic data only | See `docs/SECURITY.md` |

## Slide 3: What production would add
| Area | Production |
|---|---|
| Network | Private networking, web application firewall, no public database endpoint |
| Identity | Sign-in with the company identity provider (Entra ID), roles from it, no access code |
| SAP | Real SAP connector (reading open items, posting through an approved interface) instead of the simulated tables |
| Mail | Real Exchange / Microsoft 365 connector with a service account; real customer recipients |
| Reliability | High availability and disaster recovery, backups with tested restores, always-on capacity for fast first response |
| Operations | Central logging and alerting, monitoring dashboards, on-call, SLA reporting |
| Security | Key rotation, enforced vulnerability gates in the pipeline, penetration test, data-protection review |
| Quality | Accuracy measured on real, labelled customer mail and tuned per customer; feedback loop from analyst corrections |
