"""Rules first; the learned model gives a second opinion only when the rules are unsure."""
import re

from app.classification.inputs import ClassifierInput
from app.classification.model import TextModel, load_model
from app.classification.rules import Classification, classify_signals, from_key
from app.classification.signals import extract_signals, fold
from app.rules_defaults import CLASSIFICATION

_NO_MODEL = object()


def classify(inp: ClassifierInput, cfg: dict | None = None, model: TextModel | None | object = _NO_MODEL) -> Classification:
    """cfg: the "classification" rule (defaults if None). model: None = rules only; omitted = the saved model."""
    cfg = {**CLASSIFICATION, **(cfg or {})}
    result = classify_signals(extract_signals(inp), cfg)
    if model is _NO_MODEL:
        model = load_model()
    if model is None or result.confidence >= cfg["model_below_confidence"]:
        return result
    readable = " ".join([inp.subject, inp.body] + [d.text for d in inp.attachments])  # not file names
    if len(re.findall(r"\w", fold(readable))) < cfg["model_min_chars"]:
        result.reasons["note"] = "Too little readable text to classify - please check the e-mail and its attachments"
        return result
    if "document about AR" in result.reasons.get("note", ""):
        return result  # the model was trained on customer e-mails; it cannot judge such a document

    ranked = model.predict(inp)
    key, p = ranked[0]
    result.method = "rules+model"
    result.reasons["model"] = {"answer": key, "probability": round(p, 3),
                               "top3": [{"answer": k, "probability": round(v, 3)} for k, v in ranked[:3]],
                               "rules_answer": result.key, "rules_confidence": result.confidence}
    if key == result.key:
        result.confidence = round(max(result.confidence, min(99.0, 100 * p)), 1)
        result.reasons["model"]["decision"] = "agrees with the rules"
    elif p >= cfg["model_min_probability"] or not result.reasons["signals"]:  # rules found no wording at all
        label, rem, ptp, cat = from_key(key, cfg["both_label"])
        result.label, result.contains_remittance, result.contains_ptp, result.out_of_scope_category = label, rem, ptp, cat
        result.confidence = round(min(99.0, 100 * p), 1)
        result.reasons["model"]["decision"] = ("model answer used (rules were unsure)" if p >= cfg["model_min_probability"]
                                               else "model answer used (no wording found by the rules) - low confidence")
    else:
        result.reasons["model"]["decision"] = "rules answer kept (model not sure enough)"
    return result
