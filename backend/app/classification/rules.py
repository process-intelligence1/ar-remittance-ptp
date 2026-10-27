"""Signals -> label, flags, out-of-scope category, confidence and reasons (rules only).

Settings come from ar.rule_config key "classification" (defaults in app/rules_defaults.py):
- contains_threshold: points needed to say "this e-mail contains a remittance" / "... a promise"
- out_of_scope_threshold: points an out-of-scope category needs to win
- evidence_bonus: invoice numbers, amounts or payment references found (supports remittance/PTP)
- known_sender_bonus: sender address/domain is a customer contact in ADR6
- future_date_bonus: a date after the business date in an e-mail with promise wording
- both_label: label when an e-mail contains a remittance AND a promise (rows are split in M05)
"""
import math
from dataclasses import dataclass, field

from app.classification.signals import Hit, Signals


@dataclass
class Classification:
    label: str
    contains_remittance: bool
    contains_ptp: bool
    out_of_scope_category: str | None
    confidence: float              # 0-100
    method: str = "rules"          # rules | rules+model
    reasons: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        """One value per outcome (used by the model): REMITTANCE, PTP, MIXED, OUT_OF_SCOPE:<CATEGORY>."""
        if self.label == "OUT_OF_SCOPE":
            return f"OUT_OF_SCOPE:{self.out_of_scope_category}"
        if self.contains_remittance and self.contains_ptp:
            return "MIXED"
        return self.label


def from_key(key: str, both_label: str = "PTP") -> tuple[str, bool, bool, str | None]:
    if key.startswith("OUT_OF_SCOPE:"):
        return "OUT_OF_SCOPE", False, False, key.split(":", 1)[1]
    if key == "MIXED":
        return both_label, True, True, None
    return key, key == "REMITTANCE", key == "PTP", None


def _confidence(top: float, other: float) -> float:
    """More points -> surer; points for a competing answer -> less sure. 3 points alone ~ 63 %."""
    if top <= 0:
        return 5.0
    value = 100 * (1 - math.exp(-top / 3)) * top / (top + other)
    return round(max(5.0, min(99.0, value)), 1)


def classify_signals(s: Signals, cfg: dict) -> Classification:
    t_in, t_oos = cfg["contains_threshold"], cfg["out_of_scope_threshold"]
    rem, ptp = s.score("REMITTANCE"), s.score("PTP")
    if ptp > 0 and s.future_dates:
        s.hits.append(Hit("PTP", "date after business date", "text", s.future_dates[0], cfg["future_date_bonus"]))
        ptp += cfg["future_date_bonus"]
    evidence = 0.0
    if s.invoice_refs or s.payment_refs or s.amounts:
        evidence += cfg["evidence_bonus"]
    if s.sender_known:
        evidence += cfg["known_sender_bonus"]
    oos = s.oos_scores()
    oos_cat, oos_best = max(oos.items(), key=lambda kv: kv[1]) if oos else (None, 0.0)
    oos_second = sorted(oos.values(), reverse=True)[1] if len(oos) > 1 else 0.0
    in_scope = max(rem, ptp)
    contains_rem, contains_ptp = rem >= t_in, ptp >= t_in
    has_refs = bool(s.invoice_refs or s.payment_refs or s.amounts)
    note = None

    if rem > 0 and ptp > 0 and sum(1 for v in oos.values() if v > 0) >= cfg["document_about_ar_categories"]:
        # remittance AND promise AND several out-of-scope kinds at once: a document ABOUT AR (a dataset,
        # a spec, a presentation) rather than a customer e-mail -> out of scope, low confidence = review
        label, contains_rem, contains_ptp, category = "OUT_OF_SCOPE", False, False, "GENERAL"
        conf = 30.0
        note = "Many different kinds of wording at once - reads like a document about AR, not a customer e-mail"
    elif not (contains_rem or contains_ptp) and not has_refs and oos_best < t_oos:
        # only weak hints and no invoice number, amount or payment reference: not enough for remittance / PTP
        label, contains_rem, contains_ptp, category = "OUT_OF_SCOPE", False, False, oos_cat or "GENERAL"
        conf = 20.0
        note = "Only weak hints and no invoice number, amount or payment reference" if s.hits else None
    elif oos_best >= t_oos and oos_best >= in_scope + (evidence if in_scope else 0):
        label, contains_rem, contains_ptp, category = "OUT_OF_SCOPE", False, False, oos_cat
        conf = _confidence(oos_best, in_scope + evidence / 2 + oos_second / 2)
    elif contains_rem or contains_ptp or in_scope > 0:
        if not (contains_rem or contains_ptp):  # weak: take the bigger one
            contains_rem, contains_ptp = rem >= ptp, ptp > rem
        category = None
        if contains_rem and contains_ptp:
            label = cfg["both_label"]
            conf = _confidence(min(rem, ptp) + evidence, oos_best)
        elif contains_ptp:
            label = "PTP"
            conf = _confidence(ptp + evidence, max(oos_best, rem))
        else:
            label = "REMITTANCE"
            conf = _confidence(rem + evidence, max(oos_best, ptp))
    else:
        label, category = "OUT_OF_SCOPE", oos_cat or "GENERAL"
        conf = _confidence(oos_best, evidence) if oos_best else 20.0

    reasons = {
        "signals": [h.as_reason() for h in s.hits],
        "scores": {"remittance": rem, "ptp": ptp, "out_of_scope": oos, "evidence_bonus": evidence},
        "evidence": {"invoice_refs": s.invoice_refs[:20], "payment_refs": s.payment_refs[:10],
                     "amounts": s.amounts, "future_dates": s.future_dates[:5], "sender_known": s.sender_known},
    }
    if note:
        reasons["note"] = note
    elif not s.hits:
        reasons["note"] = "No remittance, promise or out-of-scope wording found"
    return Classification(label, contains_rem, contains_ptp, category, conf, "rules", reasons)
