# M03 — Classification

## What it does
Every e-mail that has been read (M02) is sorted into **REMITTANCE**, **PTP** (promise to pay) or
**OUT_OF_SCOPE**, with two yes/no flags, **contains remittance** and **contains PTP** (one e-mail
can have both: "we paid these… the rest will be paid on 13 November"). An out-of-scope e-mail
also gets a category from the Knowledge Base: marketing, customer service, sales inquiry,
general, vendor invoice, HR, bank notification. Every result keeps its **reasons** (which signals
fired, where, and with how many points) so the screens can show *why*.

| Where | What |
|---|---|
| `ar.email_classification` | one row per run: `label`, `contains_remittance`, `contains_ptp`, `out_of_scope_category`, `confidence` (0–100), `method` (`rules` / `rules+model`), `reasons`, `is_current` (older runs are kept as history) |
| `ar.email_message.status` | `PARSED` → `CLASSIFIED` |
| `ar.audit_log` | `EMAIL_CLASSIFIED` with the result |
| Gmail (Azure only) | label `AR-Remittance` / `AR-PTP` / `AR-OutOfScope` (the other two are removed) |

## How it works
```
 subject + clean body + every attachment's text (+ file names) + sender
   │
   ├─ 1. keyword lists (EN/DE/FR/ES/PT/JA, app/classification/lexicons.py)
   │      each phrase has points: 3 = says it on its own ("remittance advice", "we will pay",
   │      "Zahlungsavis", "お振込み予定"), 2 = strong hint, 1 = supporting hint
   │      + attachment names (Payment_Advice_…, PTP_letter_…, Zahlungszusage_…)
   │      + evidence: invoice numbers, amounts, payment references (PAY…, ZA-…, TRF…)
   │      + sender known as a customer contact (ADR6), + a date after the business date
   │
   ├─ 2. rules (rules.py): ≥ 3 remittance points → contains remittance; ≥ 3 promise points →
   │      contains PTP (both → label PTP; the rows are split per invoice in M05);
   │      an out-of-scope category wins only with ≥ 3 points and more than the in-scope points
   │      safety rules: weak hints without any invoice number / amount / reference → out of scope;
   │      remittance + promise + 3 out-of-scope kinds at once → "a document ABOUT AR" (a dataset,
   │      a spec) → out of scope, 30 %
   │
   └─ 3. confidence < 70 % → the small learned model gives a second opinion (model.py):
          TF-IDF on 2–5 letter pieces + logistic regression, trained on the 234 samples.
          Its answer is used when it is ≥ 60 % sure, or when the rules found no wording at all
          (then with low confidence). It is not asked when there is (almost) no readable text.
```
All thresholds are in `ar.rule_config` key `classification` (defaults in `backend/app/rules_defaults.py`).

**The model in the image.** scikit-learn is used only on the laptop to *train* the model. The
result is saved as plain numbers (`backend/app/classification/model.npz`, ~0.85 MB, no pickle) and
the API predicts with numpy. This keeps scikit-learn + scipy (~50 MB compressed) out of the
container image — the free GitHub image storage was already at 491 of 500 MB. A test checks that
the numpy predictions equal scikit-learn's.

## Results (honest)
Report: [`docs/reports/M03_classification_report.md`](../reports/M03_classification_report.md)
(`python -m scripts.evaluate --stage classification`).

| Check | Result |
|---|---|
| 234 samples, rules only | 234/234 (100 %) — *optimistic: the keyword lists were written while looking at these samples* |
| 234 samples, rules + model, 5-fold cross-validated (model never judges an e-mail it learned from) | 234/234 (100 %) |
| model alone, cross-validated | 221/234 (94.4 %) |
| hand-written e-mails in new wording, batch 1 (26), **first run** | 23/26 — fixed: a bug (dots inside "3.300,00" / "15.11.2026" broke German phrases) and "no wording → ask the model" |
| hand-written batch 2 (18, written after those fixes), **first run** | **rules only 8/18, rules + model 15/18 (83 %)** — then its missed phrases were added |
| both hand-written batches now | 44/44 — but they are no longer "unseen" |
| 21 real e-mails in the laptop database | 18 customer e-mails all right; 3 project e-mails ("AR - AP usecases" ×2, "Remittance HTML Prototype") were first read as remittance/PTP → three safety rules added → now out of scope at 20–30 % (= review) |

**What this means:** on the demo samples and wording like them the classifier is very reliable.
On *new* wording the first-try rate was about 83 %; uncertain results get a low confidence, so the
workbench (M05/M08) sends them to review instead of acting on them. Every miss teaches a phrase:
add it to `lexicons.py`, re-run the evaluation.

**About P03R / P05R.** BUILD_PLAN says P03R, P05R and P06 are "mixed". Reading all of them showed
that only **P06** e-mails contain a payment *and* a promise. P03R / P05R are the *payments that
follow an earlier promise* (e.g. P03-0199 promises MUM/2627/04649 + 04655 for 16 Nov; P03R-0200
pays exactly those) — their text contains no promise. They are therefore expected and classified
as REMITTANCE; linking them to the earlier promise is M10 (PTP kept).

## How to try it
From the `backend` folder (laptop):
```
python -m scripts.classify                       # e-mails read but not classified yet
python -m scripts.classify --email EML-000037    # one e-mail
python -m scripts.classify --reclassify          # all again (history kept)
python -m scripts.evaluate --stage classification   # accuracy report
python -m scripts.train_classifier               # after changing samples (needs requirements-dev.txt)
```
API: `GET /api/emails` shows each e-mail's classification (signal *names* only — no e-mail text
before the login exists). `POST /api/admin/emails/{ref}/classify` (header `X-Admin-Key`)
classifies one stored e-mail; the e-mail must be read first (`…/parse`), otherwise 409.

## Limitations
- Keyword rules + a model trained on 234 samples: new phrasing or a language outside
  EN/DE/FR/ES/PT/JA can be missed → low confidence → review. Out-of-scope categories have only 2–3
  samples each, so the model alone is weaker there; the rules carry them.
- An e-mail with both a payment and a promise is labelled PTP; the per-invoice split comes in M05.
- The "future date" hint cannot always tell 03/11/2026 (3 Nov) from US 11/03 (11 Mar): it only
  counts when every reading is in the future.
- Classification runs from the script or the admin endpoint; automatic classification of every
  new e-mail comes with the pipeline/worker (M06).
- Gmail labels are set only where Gmail is polled (Azure) or with `--gmail-labels` on the laptop.
