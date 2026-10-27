"""Knowledge Base scoring, fast paths and decisions. Every weight, band and threshold comes from
ar.rule_config (defaults in app/rules_defaults.py).

raw = invoice_match x 0.35 + amount x 0.30 + sender->company code x 0.10 + customer name x 0.05 + date x 0.10
formula confidence = raw / 0.90 (normalization_max) x 100
Fast paths (EXACT invoice match + open BSID item):
  same currency + amount within 2 %  -> 92 %      amount not stated -> 91 %
  The formula is ALWAYS calculated too: final confidence = max(fast-path value, formula), and
  confidence_source says which one it was (FAST_PATH | FORMULA). The fast path decides the category /
  decision either way - only the number shown can be higher.
Decision (KB table): >= 80 + BSID match = Auto Process; >= 80 without = Exception; 40-79 = Manual
Review; < 40 = Manual Investigation. A NONE match is always an EXCEPTION ("No BSID match found");
review reasons (NEAR match, payment block, no invoice number, ...) turn Auto Process into Manual Review.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

RECOMMENDED = {  # KB "Thresholds & Decisions": the first action of each row
    "AUTO_PROCESS": "Confirm & Update SAP",
    "EXCEPTION": "Add BSID Invoice Details",
    "MANUAL_REVIEW": "Add / Update Invoice Details",
    "MANUAL_INVESTIGATION": "Add / Update Invoice Details; Escalate to AR Supervisor",
    "DUPLICATE": "Close as Duplicate",
    "OUT_OF_SCOPE": "Ignore",
}
STATUS = {"AUTO_PROCESS": "AUTO_PROCESSED", "EXCEPTION": "EXCEPTION", "MANUAL_REVIEW": "PENDING_REVIEW",
          "MANUAL_INVESTIGATION": "PENDING_REVIEW", "DUPLICATE": "DUPLICATE", "OUT_OF_SCOPE": "IGNORED"}


@dataclass
class Score:
    invoice_match: float = 0.0
    amount_alignment: float = 0.0
    amount_difference_pct: Decimal | None = None
    sender_company: float = 0.0
    customer_name: float = 0.0
    date_difference_days: int | None = None
    date_proxy: float = 0.0
    raw: Decimal = Decimal(0)
    formula_confidence: Decimal = Decimal(0)
    fast_path: str | None = None            # EXACT_FULL_MATCH | EXACT_AMOUNT_MISSING
    fast_path_value: Decimal | None = None
    confidence: Decimal = Decimal(0)
    confidence_source: str = "FORMULA"      # FORMULA | FAST_PATH
    category: str = "LOW"                   # HIGH | MEDIUM | LOW
    decision: str = "MANUAL_INVESTIGATION"
    status: str = "PENDING_REVIEW"
    recommended_action: str | None = None
    exception_reason: str | None = None
    review_reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"invoice_match": self.invoice_match, "amount_alignment": self.amount_alignment,
                "amount_difference_pct": str(self.amount_difference_pct) if self.amount_difference_pct is not None else None,
                "sender_company": self.sender_company, "customer_name": round(self.customer_name, 4),
                "date_difference_days": self.date_difference_days, "date_proxy": self.date_proxy,
                "raw": str(self.raw), "formula_confidence": str(self.formula_confidence), "fast_path": self.fast_path,
                "confidence": str(self.confidence), "confidence_source": self.confidence_source,
                "decision": self.decision}


def _q(value: Decimal, places: str = "0.01") -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def amount_alignment(amount: Decimal | None, currency: str | None, bsid_amount: Decimal | None,
                     bsid_currency: str | None, bands: dict) -> tuple[float, Decimal | None]:
    """(score, difference in %) - currency mismatch or missing amount = 0 (KB)."""
    if amount is None or bsid_amount is None:
        return float(bands.get("missing_amount_score", 0.0)), None
    if currency and bsid_currency and currency != bsid_currency:
        return float(bands.get("currency_mismatch_score", 0.0)), None
    if bsid_amount == 0:
        return 0.0, None
    diff = abs(amount - bsid_amount) / abs(bsid_amount) * 100
    for band in bands["bands"]:
        if band["max_diff_pct"] is None or diff <= Decimal(str(band["max_diff_pct"])):
            return float(band["score"]), _q(diff, "0.0001")
    return 0.0, _q(diff, "0.0001")


def date_proxy(days: int | None, bands: dict) -> float:
    if days is None:
        return 0.0
    for band in bands["bands"]:
        if band["max_days"] is None or days <= band["max_days"]:
            return float(band["score"])
    return 0.0


def category(confidence: Decimal, thresholds: dict) -> str:
    if confidence >= thresholds["high"]:
        return "HIGH"
    return "MEDIUM" if confidence >= thresholds["medium"] else "LOW"


def score(rules: dict, *, level: str, invoice_score: float, amount: Decimal | None, currency: str | None,
          bsid_amount: Decimal | None, bsid_currency: str | None, sender_company: bool, name_similarity: float,
          date_days: int | None, item_open: bool = True, review_reasons: list[str] | None = None) -> Score:
    """Score one row against one BSID candidate (level NONE = no candidate)."""
    w = rules["scoring_weights"]
    s = Score(invoice_match=invoice_score, sender_company=1.0 if sender_company else 0.0,
              customer_name=max(0.0, min(1.0, name_similarity)), date_difference_days=date_days,
              review_reasons=list(review_reasons or []))
    s.amount_alignment, s.amount_difference_pct = amount_alignment(amount, currency, bsid_amount, bsid_currency,
                                                                   rules["amount_alignment_bands"])
    s.date_proxy = date_proxy(date_days, rules["date_proxy_bands"])
    raw = (Decimal(str(s.invoice_match)) * Decimal(str(w["invoice_match"]))
           + Decimal(str(s.amount_alignment)) * Decimal(str(w["amount_alignment"]))
           + Decimal(str(s.sender_company)) * Decimal(str(w["sender_company"]))
           + Decimal(str(s.customer_name)) * Decimal(str(w["customer_name"]))
           + Decimal(str(s.date_proxy)) * Decimal(str(w["date_proxy"])))
    s.raw = _q(raw, "0.0001")
    s.formula_confidence = _q(min(Decimal(100), raw / Decimal(str(w["normalization_max"])) * 100))

    # fast paths (EXACT + open item); confidence = max(fast-path value, formula)
    fp = rules["fast_path"]
    if fp.get("enabled", True) and level == fp.get("required_match_level", "EXACT") and item_open:
        same_currency = not (currency and bsid_currency and currency != bsid_currency)
        if amount is None and same_currency:
            s.fast_path, s.fast_path_value = "EXACT_AMOUNT_MISSING", Decimal(str(fp["exact_amount_missing_score"]))
        elif (amount is not None and same_currency and s.amount_difference_pct is not None
              and s.amount_difference_pct <= Decimal(str(fp["amount_tolerance_pct"]))):
            s.fast_path, s.fast_path_value = "EXACT_FULL_MATCH", Decimal(str(fp["exact_full_match_score"]))
    if s.fast_path_value is not None and s.fast_path_value > s.formula_confidence:
        s.confidence, s.confidence_source = _q(s.fast_path_value), "FAST_PATH"
    else:
        s.confidence, s.confidence_source = s.formula_confidence, "FORMULA"

    # decision
    th = rules["decision_thresholds"]
    s.category = "HIGH" if s.fast_path else category(s.confidence, th)
    if level == "NONE":
        s.decision, s.exception_reason = "EXCEPTION", "No BSID match found"
    elif s.category == "HIGH":
        s.decision = "MANUAL_REVIEW" if s.review_reasons else "AUTO_PROCESS"
    elif s.category == "MEDIUM":
        s.decision = "MANUAL_REVIEW"
    else:
        s.decision = "MANUAL_INVESTIGATION"
    s.status = STATUS[s.decision]
    s.recommended_action = RECOMMENDED[s.decision]
    return s


def days_between(a: date | None, b: date | None) -> int | None:
    return abs((a - b).days) if a and b else None
