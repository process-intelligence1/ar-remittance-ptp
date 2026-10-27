"""Measure accuracy against the sample folders (the folder prefix is the expected answer).

Run from the backend folder:
    python -m scripts.evaluate --stage classification   -> docs/reports/M03_classification_report.md
    python -m scripts.evaluate --stage extraction       -> docs/reports/M04_extraction_report.md
    python -m scripts.evaluate --stage matching         -> docs/reports/M05_matching_report.md

Classification is measured four ways, so the numbers are honest:
- rules only, on all samples (the keyword lists were written while looking at the samples, so
  this is the optimistic number);
- rules + model with 5-fold cross-validation: the model is trained on 4/5 of the samples and
  judges the other 1/5 - it never judges an e-mail it learned from;
- the model alone (cross-validated), for comparison;
- hand-written e-mails that are not samples (data/eval/classification_unseen.json), new wording,
  rules + model trained on all samples. Its "_about" text records which batches were used to fix
  the rules (those are no longer unseen) - add a new batch before quoting a fresh number.
A result is correct only if label, both flags and (for out of scope) the category are right.
"""
import json
import re
import sys
import time
import warnings
from collections import Counter, defaultdict
from datetime import date

from app.classification.classifier import classify
from app.classification.inputs import ClassifierInput, Document
from app.classification.model import load_model, model_text, train
from app.classification.rules import from_key
from app.classification.samples import load_corpus
from app.config import PROJECT_ROOT, get_settings
from app.rules_defaults import CLASSIFICATION

REPORT = PROJECT_ROOT / "docs" / "reports" / "M03_classification_report.md"
UNSEEN = PROJECT_ROOT / "data" / "eval" / "classification_unseen.json"
FOLDS = 5


def _known_sender_lookup():
    """ADR6 lookup when the laptop database is reachable; otherwise the signal is left out."""
    try:
        from app.classification.service import sender_known
        from app.db import SessionLocal

        db = SessionLocal()
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        return lambda addr: sender_known(db, addr), "ADR6 (laptop database)"
    except Exception as exc:
        return None, f"not used (database not reachable: {type(exc).__name__})"


def _unseen_inputs(business_date: date) -> list[tuple[str, ClassifierInput, str, int]]:
    data = json.loads(UNSEEN.read_text(encoding="utf-8"))
    return [(c["id"], ClassifierInput(c["subject"], c["body"],
                                      [Document(a["name"], a["text"]) for a in c.get("attachments", [])],
                                      business_date=business_date), c["expected"], c.get("batch", 1))
            for c in data["cases"]]


def _cross_validated(corpus, cfg):
    """Rules+model and model-only answers, each e-mail judged by a model that did not see it."""
    from sklearn.model_selection import StratifiedKFold

    texts = [model_text(inp) for _, inp, _ in corpus]
    keys = [exp.key for _, _, exp in corpus]
    combined, model_only = [None] * len(corpus), [None] * len(corpus)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # some out-of-scope categories have fewer than 5 samples
        for train_idx, test_idx in StratifiedKFold(FOLDS, shuffle=True, random_state=42).split(texts, keys):
            m = train([texts[i] for i in train_idx], [keys[i] for i in train_idx])
            for i in test_idx:
                combined[i] = classify(corpus[i][1], cfg, model=m)
                model_only[i] = m.predict(corpus[i][1])[0][0]
    return combined, model_only


def _pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f} %" if d else "-"


def classification() -> int:
    started = time.perf_counter()
    cfg = dict(CLASSIFICATION)
    business_date = get_settings().business_date
    lookup, lookup_note = _known_sender_lookup()
    print("Reading the sample folders (cached text is reused) ...", flush=True)
    corpus = load_corpus(known_sender=lookup, business_date=business_date, progress=True)
    n = len(corpus)

    rules = [classify(inp, cfg, model=None) for _, inp, _ in corpus]
    print("Cross-validating the model ...", flush=True)
    combined, model_only = _cross_validated(corpus, cfg)
    expected = [exp for _, _, exp in corpus]
    ok = lambda results: [r.key == e.key for r, e in zip(results, expected)]
    ok_rules, ok_comb = ok(rules), ok(combined)
    ok_model = [k == e.key for k, e in zip(model_only, expected)]
    label_ok = lambda results: sum(r.label == e.label for r, e in zip(results, expected))

    full_model = load_model()
    unseen = _unseen_inputs(business_date)
    un_rules = [classify(u[1], cfg, model=None) for u in unseen]
    un_comb = [classify(u[1], cfg, model=full_model) for u in unseen] if full_model else un_rules
    un_ok_rules = [r.key == u[2] for r, u in zip(un_rules, unseen)]
    un_ok_comb = [r.key == u[2] for r, u in zip(un_comb, unseen)]

    def unseen_rows(batch: int, oks: list[bool]) -> tuple[int, int]:
        picked = [ok for ok, u in zip(oks, unseen) if u[3] == batch]
        return sum(picked), len(picked)

    # ---------------------------------------------------------------- report
    L = ["# M03 — classification report", "",
         f"{n} sample e-mails (expected answer = folder prefix), business date {business_date}, "
         f"sender check: {lookup_note}. Run time {time.perf_counter() - started:.0f} s.", "",
         "A result counts as correct only when the label, both flags (contains remittance / contains PTP) "
         "and, for out of scope, the category are all right.", "",
         "## Accuracy", "",
         "| Method | Correct | Accuracy | Label only |", "|---|---|---|---|",
         f"| Rules only (optimistic: keywords written while looking at these samples) | {sum(ok_rules)}/{n} | "
         f"**{_pct(sum(ok_rules), n)}** | {_pct(label_ok(rules), n)} |",
         f"| Rules + model, {FOLDS}-fold cross-validated (the model never judges an e-mail it learned from) | "
         f"{sum(ok_comb)}/{n} | **{_pct(sum(ok_comb), n)}** | {_pct(label_ok(combined), n)} |",
         f"| Model alone, cross-validated (for comparison) | {sum(ok_model)}/{n} | {_pct(sum(ok_model), n)} | "
         f"{_pct(sum(from_key(k)[0] == e.label for k, e in zip(model_only, expected)), n)} |",
    ]
    for batch in sorted({u[3] for u in unseen}):
        for name, oks in (("rules only", un_ok_rules), ("rules + model", un_ok_comb)):
            good, tot = unseen_rows(batch, oks)
            L.append(f"| Hand-written e-mails (not samples), batch {batch}, {name} | {good}/{tot} | {_pct(good, tot)} | |")
    L += ["", f"About the hand-written e-mails: {json.loads(UNSEEN.read_text(encoding='utf-8'))['_about']}", "",
         f"The model was asked for {sum(r.method == 'rules+model' for r in combined)} of {n} samples "
         f"(rules confidence below {cfg['model_below_confidence']} %)."]

    labels = ["REMITTANCE", "PTP", "OUT_OF_SCOPE"]
    per_type = lambda oks: [f"{sum(ok for ok, e in zip(oks, expected) if e.label == t)}/"
                            f"{sum(e.label == t for e in expected)}" for t in labels]
    L += ["", "## Accuracy per type (expected type; PTP includes the P06 e-mails with payment + promise)", "",
          "| Method | " + " | ".join(labels) + " |", "|---|" + "---|" * len(labels)]
    for name, oks in (("Rules only", ok_rules), ("Rules + model, cross-validated", ok_comb),
                      ("Model alone, cross-validated", ok_model)):
        L.append(f"| {name} | " + " | ".join(per_type(oks)) + " |")
    model_misses = [(c, e.key, k) for (c, _, e), k in zip(corpus, model_only) if k != e.key]
    L += ["", f"Model alone, cross-validated - misses ({len(model_misses)}); this is why the rules decide and the "
          "model is only asked when the rules are unsure:", ""]
    L += ["None."] if not model_misses else [f"- {c}: expected {e}, model said {k}" for c, e, k in model_misses]

    conf = Counter((e.label, r.label) for r, e in zip(combined, expected))
    L += ["", "## Confusion matrix (rules + model, cross-validated)", "",
          "| Expected \\ Result | " + " | ".join(labels) + " |", "|---|" + "---|" * len(labels)]
    L += [f"| {a} | " + " | ".join(str(conf[(a, b)]) for b in labels) + " |" for a in labels]

    L += ["", "## E-mails with remittance AND promise", "",
          "| Sample | Label | Contains remittance | Contains PTP | Confidence | Correct |", "|---|---|---|---|---|---|"]
    for (code, _, e), r, good in zip(corpus, combined, ok_comb):
        if code.startswith(("P03R", "P05R", "P06")):
            L.append(f"| {code} | {r.label} | {'yes' if r.contains_remittance else 'no'} | "
                     f"{'yes' if r.contains_ptp else 'no'} | {r.confidence} | {'✅' if good else '❌'} |")
    L += ["", "P06 e-mails pay some invoices and promise the rest, so both flags must be set. "
          "P03R / P05R are the payments that follow an earlier promise (P03 / P05): their bodies and "
          "attachments contain only the payment (checked by reading all six), so the expected answer is "
          "REMITTANCE with no promise; linking them to the earlier promise is M10 (PTP kept)."]

    by_scn = defaultdict(list)
    for (code, _, _), r, good in zip(corpus, combined, ok_comb):
        by_scn[code.split("-")[0]].append((good, r.confidence))
    L += ["", "## Per scenario (rules + model, cross-validated)", "",
          "| Scenario | E-mails | Correct | Avg confidence |", "|---|---|---|---|"]
    for scn in sorted(by_scn):
        rows = by_scn[scn]
        L.append(f"| {scn} | {len(rows)} | {sum(g for g, _ in rows)} | {sum(c for _, c in rows) / len(rows):.1f} |")

    def _signals(r) -> str:
        return ", ".join(f"{h['signal']} ({h['class'].replace('OUT_OF_SCOPE:', 'OOS:').lower()})"
                         for h in r.reasons.get("signals", [])) or "none"

    L += ["", "## Misses (rules + model, cross-validated)", ""]
    misses = [(c, e, r) for (c, _, e), r, g in zip(corpus, combined, ok_comb) if not g]
    L += ["None."] if not misses else ["| Sample | Expected | Result | Confidence | Signals |", "|---|---|---|---|---|"] + [
        f"| {c} | {e.key} | {r.key} | {r.confidence} | {_signals(r)} |" for c, e, r in misses]

    asked = [(c, r) for (c, _, _), r in zip(corpus, combined) if r.method == "rules+model"]
    L += ["", "## Where the model was asked", ""]
    L += ["None."] if not asked else ["| Sample | Rules said | Model said | Final | Decision |", "|---|---|---|---|---|"] + [
        f"| {c} | {r.reasons['model']['rules_answer']} ({r.reasons['model']['rules_confidence']}) | "
        f"{r.reasons['model']['answer']} ({r.reasons['model']['probability']}) | {r.key} ({r.confidence}) | "
        f"{r.reasons['model']['decision']} |" for c, r in asked]

    L += ["", "## Hand-written e-mails (rules + model trained on all samples)", "",
          "| Id | Batch | Subject | Expected | Result | Confidence | Method | Correct | Signals |", "|---|---|---|---|---|---|---|---|---|"]
    for (uid, inp, e, batch), r, good in zip(unseen, un_comb, un_ok_comb):
        L.append(f"| {uid} | {batch} | {inp.subject.replace('|', '/')} | {e} | {r.key} | {r.confidence} | {r.method} | "
                 f"{'✅' if good else '❌'} | {_signals(r)} |")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"rules {sum(ok_rules)}/{n}, rules+model (cv) {sum(ok_comb)}/{n}, model (cv) {sum(ok_model)}/{n}, "
          f"unseen batch 1 rules+model {'/'.join(map(str, unseen_rows(1, un_ok_comb)))}, "
          f"unseen batch 2 rules {'/'.join(map(str, unseen_rows(2, un_ok_rules)))}, "
          f"rules+model {'/'.join(map(str, unseen_rows(2, un_ok_comb)))}")
    print(f"Report: {REPORT}")
    return 0


# --------------------------------------------------------------------------- extraction (M04)
EXTRACTION_REPORT = PROJECT_ROOT / "docs" / "reports" / "M04_extraction_report.md"
UNREFERENCED = ("R12", "R13", "R28")  # payments without invoice numbers by design (M05 finds them by amount)


def extraction() -> int:
    """Lines judged against BSID (no hand-made answers exist): number in BSID (XBLNR, or exactly
    BELNR / VBELN) and amount within 2 % of the BSID amount (or the gross, when a deduction was taken).
    Dev = the 2/3 the rules were written on; HELD-OUT = every 3rd sample per scenario, never studied."""
    from decimal import Decimal

    from sqlalchemy import text as sql

    from app.db import SessionLocal
    from app.extraction.documents import SOURCE_LABELS
    from app.extraction.extractor import extract
    from app.extraction.refs import normalise_ref
    from app.extraction.samples import load_all, split
    from app.rules_defaults import EXTRACTION

    started = time.perf_counter()
    tol = Decimal(str(EXTRACTION["amount_tolerance_pct"])) / 100
    with SessionLocal() as db:
        bsid: dict[str, list[tuple[str, Decimal]]] = defaultdict(list)
        for x, b, v, w, amt, sh in db.execute(sql("select xblnr, belnr, vbeln, waers, wrbtr, shkzg from sap.bsid")):
            a = -amt if sh == "H" else amt
            for f in {x, b, v} - {None}:
                bsid[normalise_ref(f)].append((w, a))
    print("Reading the sample folders (cached) and extracting ...", flush=True)
    items = load_all()
    parts = split([c for c, _ in items])

    rows, emails = [], []
    for code, inp in items:
        if code.startswith("O"):
            continue
        r = extract(inp)
        scn = code.split("-")[0]
        emails.append({"code": code, "scn": scn, "part": parts[code], "r": r, "inp": inp})
        for ln in r.lines:
            hits = bsid.get(ln.ref_norm, [])

            def near(v):
                return v is not None and any(abs(v - a) <= abs(a) * tol for _, a in hits)

            if not hits:
                cat = "NOT_IN_BSID"
            elif ln.amount is None:
                cat = "NO_AMOUNT"
            elif near(ln.amount):
                cat = "EXACT"
            elif near(ln.gross):
                cat = "GROSS"           # deduction taken (TDS, charges)
            elif any(0 < ln.amount < a for _, a in hits) or ln.instalment_no:
                cat = "PARTIAL"         # short payment / instalment / partly paid
            else:
                cat = "OTHER_AMOUNT"    # overpayment, other currency, misread
            rows.append({"code": code, "scn": scn, "part": parts[code], "ln": ln, "cat": cat,
                         "kind": ln.source.kind, "bsid": hits[:2]})

    def pct(n, d):
        return f"{100 * n / d:.1f} %" if d else "-"

    def referenced_rem(x):
        return x["ln"].line_type == "REMITTANCE" and x["scn"] not in UNREFERENCED

    L = ["# M04 — extraction report", "",
         f"{len(emails)} in-scope sample e-mails ({sum(e['part'] == 'heldout' for e in emails)} held out), "
         f"{len(rows)} invoice lines extracted. Judged against BSID (4,840 open items): there are no hand-made "
         "answers, so a line counts as a **hit** when its invoice number exists in BSID (XBLNR, or exactly BELNR / "
         "VBELN) and its amount is within 2 % of the BSID amount (or its gross amount is, when a deduction was "
         f"taken). Run time {time.perf_counter() - started:.0f} s.", "",
         "**Dev** = the two thirds of the samples the rules were written on. **Held-out** = every 3rd sample of "
         "each scenario, never looked at while writing the rules - the honest number.", "",
         "## Headline (referenced remittance lines; R12, R13, R28 have no invoice numbers by design)", "",
         "| Set | Lines | Number in BSID | Strict hit (number + amount within 2 %) | Hit or deliberate part-payment |",
         "|---|---|---|---|---|"]
    for part in ("dev", "heldout", None):
        sel = [x for x in rows if referenced_rem(x) and (part is None or x["part"] == part)]
        inb = sum(x["cat"] != "NOT_IN_BSID" for x in sel)
        hit = sum(x["cat"] in ("EXACT", "GROSS") for x in sel)
        hp = sum(x["cat"] in ("EXACT", "GROSS", "PARTIAL") for x in sel)
        name = {"dev": "Dev", "heldout": "**Held-out**", None: "All"}[part]
        L.append(f"| {name} | {len(sel)} | {pct(inb, len(sel))} | **{pct(hit, len(sel))}** | {pct(hp, len(sel))} |")

    # scenarios where not one line matches BSID: built as exceptions (amount missing, unknown numbers, ...)
    by_scn = defaultdict(list)
    for x in rows:
        if referenced_rem(x):
            by_scn[x["scn"]].append(x)
    no_match = sorted(s for s, xs in by_scn.items() if not any(x["cat"] in ("EXACT", "GROSS") for x in xs))
    for part in ("dev", "heldout"):
        sel = [x for x in rows if referenced_rem(x) and x["part"] == part and x["scn"] not in no_match]
        L.append(f"| {'Dev' if part == 'dev' else '**Held-out**'} without {', '.join(no_match)} | {len(sel)} | "
                 f"{pct(sum(x['cat'] != 'NOT_IN_BSID' for x in sel), len(sel))} | "
                 f"**{pct(sum(x['cat'] in ('EXACT', 'GROSS') for x in sel), len(sel))}** | "
                 f"{pct(sum(x['cat'] in ('EXACT', 'GROSS', 'PARTIAL') for x in sel), len(sel))} |")
    L += ["", f"The last rows leave out the scenarios in which **not a single line** matches BSID ({', '.join(no_match)}): "
          "they are built as exceptions (amount column empty, invoice numbers that do not exist, payment in another "
          "currency, ...), which M05 must send to review - not reading errors. The strict number above is the one "
          "BUILD_PLAN asks for; most of its misses are deliberate part-payments (see PARTIAL per scenario)."]

    def consistent(e):
        return e["r"].total_mismatch is not None and abs(e["r"].total_mismatch) <= Decimal("0.01")

    rem_emails = [e for e in emails if e["inp"].contains_remittance and e["scn"] not in UNREFERENCED]
    parts_txt = []
    for n, key in (("dev", "dev"), ("held-out", "heldout")):
        sel = [e for e in rem_emails if e["part"] == key]
        parts_txt.append(f"{n} {pct(sum(consistent(e) for e in sel), len(sel))} ({sum(consistent(e) for e in sel)}/{len(sel)})")
    L += ["", "**Read correctly by the document's own numbers** (remittance e-mails whose lines add up exactly to the "
          "stated total): " + ", ".join(parts_txt) + ". The others state no total, or a line was missed / misread "
          "(both listed below).", "",
          "Line categories: EXACT = amount within 2 % of BSID; GROSS = gross within 2 % (deduction taken); "
          "PARTIAL = less than the open amount (short payment / instalment - deliberate in many samples); "
          "OTHER_AMOUNT = more than BSID, another currency, or misread; NO_AMOUNT = number only (e.g. a promise "
          "without a per-invoice amount); NOT_IN_BSID = no such invoice number (unknown invoice or OCR misread - "
          "M05 decides NEAR / NONE)."]

    cats = ["EXACT", "GROSS", "PARTIAL", "OTHER_AMOUNT", "NO_AMOUNT", "NOT_IN_BSID"]
    L += ["", "## Per scenario (all lines)", "", "| Scenario | E-mails | Lines | " + " | ".join(cats) + " | Hit | No lines |",
          "|---|---|---|" + "---|" * (len(cats) + 2)]
    for scn in sorted({e["scn"] for e in emails}):
        sel = [x for x in rows if x["scn"] == scn]
        es = [e for e in emails if e["scn"] == scn]
        c = Counter(x["cat"] for x in sel)
        L.append(f"| {scn} | {len(es)} | {len(sel)} | " + " | ".join(str(c[k]) for k in cats) +
                 f" | {pct(c['EXACT'] + c['GROSS'], len(sel))} | {sum(not e['r'].lines for e in es)} |")

    L += ["", "## Hit-rate per source (where the line's values came from; referenced remittance lines)", "",
          "| Source | Lines | Number in BSID | Strict hit | Hit or part-payment |", "|---|---|---|---|---|"]
    for kind, label in SOURCE_LABELS.items():
        sel = [x for x in rows if referenced_rem(x) and x["kind"] == kind]
        if sel:
            L.append(f"| {label} | {len(sel)} | {pct(sum(x['cat'] != 'NOT_IN_BSID' for x in sel), len(sel))} | "
                     f"{pct(sum(x['cat'] in ('EXACT', 'GROSS') for x in sel), len(sel))} | "
                     f"{pct(sum(x['cat'] in ('EXACT', 'GROSS', 'PARTIAL') for x in sel), len(sel))} |")

    ptp = [x for x in rows if x["ln"].line_type == "PTP"]
    L += ["", "## Promises (PTP lines)", "",
          f"{len(ptp)} PTP lines; promise date found for {sum(x['ln'].promise_date is not None for x in ptp)}; "
          f"instalment lines {sum(x['ln'].instalment_no is not None for x in ptp)}; number in BSID "
          f"{pct(sum(x['cat'] != 'NOT_IN_BSID' for x in ptp), len(ptp))}."]

    no_lines = [e for e in emails if not e["r"].lines]
    L += ["", f"## E-mails with no lines found ({len(no_lines)})", ""]
    L += ["None."] if not no_lines else [
        f"- {e['code']} ({e['part']}){' - no invoice numbers by design' if e['scn'] in UNREFERENCED else ''}"
        for e in no_lines]

    mism = [e for e in emails if e["r"].total_mismatch is not None and abs(e["r"].total_mismatch) > Decimal("0.01")]
    no_total = [e for e in rem_emails if e["r"].lines and e["r"].header.total is None]
    L += ["", f"## Total vs sum of lines - mismatches ({len(mism)})", ""]
    L += ["None."] if not mism else ["| Sample | Set | Total | Sum of lines | Difference |", "|---|---|---|---|---|"] + [
        f"| {e['code']} | {e['part']} | {e['r'].header.total} {e['r'].header.payment_currency or ''} | "
        f"{e['r'].lines_sum} | {e['r'].total_mismatch} |" for e in mism]
    L += ["", f"Remittance e-mails with lines but no stated total (cannot be checked): {len(no_total)} - "
          + ", ".join(e["code"] for e in no_total[:40])]

    fails = [x for x in rows if x["cat"] in ("NOT_IN_BSID", "OTHER_AMOUNT")]
    L += ["", f"## Lines to look at ({len(fails)}: number not in BSID, or amount above BSID / other currency)", "",
          "| Sample | Set | Number as read | Amount | Currency | Category | BSID | Source | Method |",
          "|---|---|---|---|---|---|---|---|---|"]
    for x in fails:
        ln = x["ln"]
        bs = "; ".join(f"{a} {w}" for w, a in x["bsid"]) or "-"
        L.append(f"| {x['code']} | {x['part']} | {ln.ref_raw} | {ln.amount} | {ln.payment_currency or ''} | {x['cat']} | "
                 f"{bs} | {SOURCE_LABELS.get(x['kind'], x['kind'])} | {ln.method} |")

    EXTRACTION_REPORT.parent.mkdir(parents=True, exist_ok=True)
    EXTRACTION_REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    for part in ("dev", "heldout"):
        sel = [x for x in rows if referenced_rem(x) and x["part"] == part]
        print(f"{part}: {len(sel)} referenced remittance lines, strict hit "
              f"{pct(sum(x['cat'] in ('EXACT', 'GROSS') for x in sel), len(sel))}, number in BSID "
              f"{pct(sum(x['cat'] != 'NOT_IN_BSID' for x in sel), len(sel))}, hit or part-payment "
              f"{pct(sum(x['cat'] in ('EXACT', 'GROSS', 'PARTIAL') for x in sel), len(sel))}")
    print(f"Report: {EXTRACTION_REPORT}")
    return 0


STAGES = {"classification": classification, "extraction": extraction}

# --------------------------------------------------------------------------- matching (M05)
MATCHING_REPORT = PROJECT_ROOT / "docs" / "reports" / "M05_matching_report.md"
DECISIONS = ["AUTO_PROCESS", "MANUAL_REVIEW", "MANUAL_INVESTIGATION", "EXCEPTION", "DUPLICATE", "OUT_OF_SCOPE"]


def matching() -> int:
    """All samples, in date order, through classification -> extraction -> matching (in memory, nothing saved);
    duplicates are checked against the earlier samples, as they would be in the database."""
    from datetime import datetime, timezone
    from decimal import Decimal

    from app.classification.samples import TextCache, load_input
    from app.db import SessionLocal
    from app.extraction.extractor import extract
    from app.extraction.samples import load_all, split
    from app.gmail.sample_sender import load_sample
    from app.matching.adapters import from_result
    from app.matching.data import load_sap
    from app.matching.duplicates import RowKey, find_original
    from app.matching.matcher import mark_duplicate, match_email, set_clusters
    from app.matching.service import all_rules
    from app.models.ar import EmailAttachment  # noqa: F401  (models loaded)
    import hashlib

    started = time.perf_counter()
    with SessionLocal() as db:
        sap = load_sap(db)
        rules = all_rules(db)
    bd = get_settings().business_date
    print("Reading the sample folders (cached), classifying, extracting, matching ...", flush=True)
    items = load_all()
    parts = split([c for c, _ in items])
    tc = TextCache()

    def received(code):
        try:
            return datetime.strptime(load_sample(code).headers.get("date", "")[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    def hashes(code):
        return frozenset(hashlib.sha256(p.read_bytes()).hexdigest() for p in load_sample(code).attachments)

    stream = sorted(items, key=lambda ci: (received(ci[0]) or datetime.min.replace(tzinfo=timezone.utc), ci[0]))
    history, clusters, results = [], [], []
    for code, inp in stream:
        cls = classify(load_input(code, tc))
        r = extract(inp)
        when = received(code)
        sender_name = None
        mi = from_result(code, inp, r, out_of_scope_category=cls.out_of_scope_category, received_at=when,
                         business_date=bd, sender_name=sender_name)
        rows = match_email(mi, sap, rules)
        dom = (inp.sender_domain or "")
        my_hashes = hashes(code)
        for n, row in enumerate(rows):
            if row.final_classification != "OUT_OF_SCOPE":
                key = RowKey(f"{code}#{n}", code, row.line.ref_norm if row.line else None, row.kunnr, row.amount,
                             row.currency, dom, when, my_hashes, row.line_type)
                orig, reason = find_original(key, history, rules["duplicate_detection"])
                if orig:
                    mark_duplicate(row, orig.row_id, reason, rules, bd)
                set_clusters(row, clusters, int(rules["customer_identification"]["cluster_min_history"]), dom)
        for n, row in enumerate(rows):
            if row.final_classification not in ("OUT_OF_SCOPE", "DUPLICATE"):
                history.append(RowKey(f"{code}#{n}", code, row.line.ref_norm if row.line else None, row.kunnr,
                                      row.amount, row.currency, dom, when, my_hashes, row.line_type))
                if row.kunnr:
                    clusters.append((row.kunnr, dom, row.currency))
        results.append({"code": code, "scn": code.split("-")[0], "part": parts[code], "rows": rows, "mi": mi,
                        "r": r})
    tc.save()

    def pct(n, d):
        return f"{100 * n / d:.1f} %" if d else "-"

    all_rows = [(x, row) for x in results for row in x["rows"]]
    L = ["# M05 — matching report", "",
         f"{len(results)} sample e-mails processed in date order (classification -> extraction -> matching, nothing "
         f"saved), {len(all_rows)} work items. Duplicates are checked against the earlier samples. "
         f"Run time {time.perf_counter() - started:.0f} s.", "",
         "Confidence = max(fast-path value, formula); the fast path decides the category / decision. "
         "**Held-out** = every 3rd sample per scenario (never studied while writing M04's rules).", "",
         "## Decision distribution", "",
         "| Set | Rows | " + " | ".join(DECISIONS) + " |", "|---|---|" + "---|" * len(DECISIONS)]
    for part in ("dev", "heldout", None):
        sel = [row for x, row in all_rows if part is None or x["part"] == part]
        c = Counter(row.score.decision for row in sel)
        name = {"dev": "Dev", "heldout": "**Held-out**", None: "All"}[part]
        L.append(f"| {name} | {len(sel)} | " + " | ".join(f"{c[d]} ({pct(c[d], len(sel))})" for d in DECISIONS) + " |")

    src = Counter((row.score.confidence_source, bool(row.score.fast_path)) for _, row in all_rows
                  if row.score.decision != "OUT_OF_SCOPE")
    L += ["", f"Confidence source: fast path applied to {sum(n for (s, fp), n in src.items() if fp)} rows - the stored "
          f"value came from the FAST_PATH for {src[('FAST_PATH', True)]} and from the higher FORMULA for "
          f"{src[('FORMULA', True)]}; {sum(n for (s, fp), n in src.items() if not fp)} rows had no fast path (formula)."]

    L += ["", "## Decision distribution per scenario", "",
          "| Scenario | E-mails | Rows | " + " | ".join(DECISIONS) + " | Main review / exception reasons |",
          "|---|---|---|" + "---|" * len(DECISIONS) + "---|"]
    for scn in sorted({x["scn"] for x in results}):
        xs = [x for x in results if x["scn"] == scn]
        sel = [row for x in xs for row in x["rows"]]
        c = Counter(row.score.decision for row in sel)
        reasons = Counter()
        for row in sel:
            for rr in row.score.review_reasons:
                if "but the e-mail comes from customer" in rr:
                    reasons["invoice of another customer than the sender"] += 1
                else:
                    reasons[rr.split(" (")[0].strip()] += 1  # without the per-row detail in brackets
            if row.score.exception_reason:
                reasons[row.score.exception_reason] += 1
            if row.duplicate_reason:
                reasons["duplicate: " + row.duplicate_reason.split(" within")[0]] += 1
            if (row.score.decision in ("MANUAL_REVIEW", "MANUAL_INVESTIGATION") and not row.score.review_reasons
                    and row.score.amount_alignment < 1):
                reasons["amount differs from BSID" if row.score.amount_alignment > 0 or row.score.amount_difference_pct
                        else "amount / currency differs from BSID"] += 1
        L.append(f"| {scn} | {len(xs)} | {len(sel)} | " + " | ".join(str(c[d]) for d in DECISIONS) + " | "
                 + "; ".join(f"{k} ({v})" for k, v in reasons.most_common(3)) + " |")

    # customer identification - checked against what the e-mail itself says
    inscope = [x for x in results if x["mi"].label != "OUT_OF_SCOPE"]
    checks = {"sender address in ADR6": [], "quoted customer number": [], "customers of exactly matched invoices": []}
    methods = Counter()
    for x in inscope:
        row = x["rows"][0]
        cust = row.customer
        methods[cust.method if cust else None] += 1
        got = cust.kunnr if cust else None
        addr = sap.by_address.get((x["mi"].sender_email or "").lower(), set())
        if len(addr) == 1:
            truth = next(iter(addr))
            checks["sender address in ADR6"].append(got == truth or truth in sap.paid_by.get(got or "", set())
                                                    or got in sap.paid_by.get(truth, set()))
        num = sap.find_kunnr(x["mi"].customer_number)
        if num:
            checks["quoted customer number"].append(got == num or num in sap.paid_by.get(got or "", set())
                                                    or got in sap.paid_by.get(num, set()))
        exact = {r.item.kunnr for r in x["rows"] if r.match and r.match.level == "EXACT"}
        if len(exact) == 1:
            checks["customers of exactly matched invoices"].append(got == next(iter(exact)))
    identified = sum(1 for x in inscope if x["rows"][0].customer and x["rows"][0].customer.kunnr)
    L += ["", "## Customer identification", "",
          f"Identified for **{identified} of {len(inscope)}** in-scope e-mails ({pct(identified, len(inscope))}). "
          "Method used: " + ", ".join(f"{k or 'none'} {v}" for k, v in methods.most_common()) + ".", "",
          "| Checked against | E-mails where it is known | Same customer |", "|---|---|---|"]
    for name, oks in checks.items():
        L.append(f"| {name} | {len(oks)} | **{pct(sum(oks), len(oks))}** ({sum(oks)}) |")
    third = [x["code"] for x in inscope if any("but the e-mail comes from customer" in rr for row in x["rows"]
                                               for rr in row.score.review_reasons)]
    L += ["", "Both checks count a payer relationship (KNVP RG, e.g. a holding company paying for its subsidiary) as "
          "the same customer. The row's customer is the OWNER of the matched invoice; when the sender is a different, "
          f"unrelated customer the row goes to review (\"Invoice belongs to customer X, but the e-mail comes from "
          f"customer Y\"): {len(third)} e-mails - " + (", ".join(third) or "none") + ".", "",
          "Not identified (unknown sender, no unique invoice owner): " + (", ".join(
              x["code"] for x in inscope if not (x["rows"][0].customer and x["rows"][0].customer.kunnr)) or "none") + "."]

    # the two BUILD_PLAN checks
    p03 = next(x for x in results if x["code"] == "P03-0193")
    r03 = next((row for row in p03["rows"] if row.line and row.line.ref_raw == "JP-26-002271"), None)
    dups = [(x["code"], row) for x, row in all_rows if row.score.decision == "DUPLICATE"]
    L += ["", "## Checks", "",
          f"- **JP-26-002271 (P03-0193)** -> customer {r03.kunnr if r03 else '-'}, {r03.amount if r03 else '-'} "
          f"{r03.currency if r03 else ''}, match {r03.match.level if r03 and r03.match else '-'}, confidence "
          f"{r03.score.confidence if r03 else '-'} % ({r03.score.confidence_source if r03 else '-'}; formula "
          f"{r03.score.formula_confidence if r03 else '-'} %), decision {r03.score.decision if r03 else '-'}: "
          + ("**OK**" if r03 and r03.kunnr == "0000102419" and r03.amount == Decimal("8300.00") and r03.currency == "SGD"
             else "**NOT OK**"),
          f"- **Duplicates found in the sample stream:** {len(dups)} rows in "
          + ", ".join(sorted({c for c, _ in dups})) + " (the re-sent sample test - the same e-mail stored twice - is "
          "in tests/test_matching.py::test_resent_sample_becomes_duplicate).", ""]
    for code, row in dups[:20]:
        L.append(f"  - {code} line {row.line_no} ({row.line.ref_raw if row.line else '-'}) = duplicate of "
                 f"{row.duplicate_of}: {row.duplicate_reason}")

    # every row that is not auto-processed, for review of the rules
    L += ["", "## Rows that are not auto-processed", "",
          "| Sample | Set | Invoice | Customer | Level | Formula | Final | Source | Decision | Reason |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for x, row in all_rows:
        s = row.score
        if s.decision in ("AUTO_PROCESS", "OUT_OF_SCOPE"):
            continue
        why = "; ".join(s.review_reasons) or s.exception_reason or row.duplicate_reason or (
            f"amount {s.amount_difference_pct} % off" if s.amount_difference_pct is not None else "amount / currency differs")
        L.append(f"| {x['code']} | {x['part']} | {row.line.ref_raw if row.line and row.line.ref_raw else '-'} | "
                 f"{(row.kunnr or '-').lstrip('0')} | {row.match.level if row.match else row.match_type or '-'} | "
                 f"{s.formula_confidence} | {s.confidence} | {s.confidence_source} | {s.decision} | {why.replace('|', '/')} |")

    MATCHING_REPORT.parent.mkdir(parents=True, exist_ok=True)
    MATCHING_REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    c = Counter(row.score.decision for _, row in all_rows)
    print(f"{len(all_rows)} rows: {dict(c)}")
    print(f"customer identified {identified}/{len(inscope)}; " + "; ".join(
        f"{n}: {pct(sum(o), len(o))}" for n, o in checks.items()))
    print(f"P03-0193: {r03.kunnr if r03 else None} {r03.amount if r03 else None} {r03.currency if r03 else None} "
          f"{r03.score.decision if r03 else None}; duplicates in stream: {len(dups)}")
    print(f"Report: {MATCHING_REPORT}")
    return 0


STAGES["matching"] = matching

if __name__ == "__main__":
    stage = sys.argv[sys.argv.index("--stage") + 1] if "--stage" in sys.argv else None
    if stage not in STAGES:
        print("Usage: python -m scripts.evaluate --stage classification|extraction|matching")
        sys.exit(2)
    sys.exit(STAGES[stage]())
