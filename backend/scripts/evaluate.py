"""Measure accuracy against the sample folders (the folder prefix is the expected answer).

Run from the backend folder:
    python -m scripts.evaluate --stage classification   -> docs/reports/M03_classification_report.md

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


if __name__ == "__main__":
    if "--stage" not in sys.argv or sys.argv[sys.argv.index("--stage") + 1] != "classification":
        print("Usage: python -m scripts.evaluate --stage classification")
        sys.exit(2)
    sys.exit(classification())
