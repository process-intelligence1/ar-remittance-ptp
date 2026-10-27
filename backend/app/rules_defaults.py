"""Default business rules, taken from the prototype's Knowledge Base.

These are copied into the ar.rule_config table by `python -m scripts.seed_app`.
After that, the database copy is the one the app uses (and the AR Supervisor can
change it from the screens). Edit here only to change the factory defaults.
"""

IGNORED_SENDERS = {
    # a domain also covers its sub-domains (mail.anthropic.com, accountprotection.microsoft.com, ...)
    "domains": ["github.com", "google.com", "accounts.google.com", "microsoft.com", "azure.com",
                "anthropic.com", "claude.ai", "claude.com"],
    # shell-style patterns on the full address (* = anything)
    "patterns": ["no-reply@*", "noreply@*"],
}

DEFAULT_RULES: dict[str, tuple[dict, str]] = {
    "ignored_senders": (
        IGNORED_SENDERS,
        "System senders whose e-mails are NOT stored: only an audit entry and the Gmail label AR-Ignored.",
    ),
    "scoring_weights": (
        {"digit_evidence": 0.35, "amount_alignment": 0.30, "sender_company": 0.10,
         "customer_name": 0.05, "date_proxy": 0.10, "normalization_max": 0.90},
        "Confidence formula weights. Raw score is divided by normalization_max to give 0-100%.",
    ),
    "digit_evidence_bands": (
        {"bands": [{"min_digits": 10, "score": 1.00, "label": "Exact 10-digit match"},
                   {"min_digits": 8, "score": 0.90, "label": "Strong partial match"},
                   {"min_digits": 7, "score": 0.82, "label": "Partial match"},
                   {"min_digits": 6, "score": 0.70, "label": "Weak partial match"},
                   {"min_digits": 0, "score": 0.00, "label": "No reliable match"}]},
        "Score for how many invoice digits / reference characters match the BSID item.",
    ),
    "amount_alignment_bands": (
        {"bands": [{"max_diff_pct": 2, "score": 1.00}, {"max_diff_pct": 5, "score": 0.80},
                   {"max_diff_pct": 10, "score": 0.60}, {"max_diff_pct": 20, "score": 0.30},
                   {"max_diff_pct": None, "score": 0.00}],
         "currency_mismatch_score": 0.0, "missing_amount_score": 0.0},
        "Score for how close the e-mail amount is to the BSID amount (same currency only).",
    ),
    "date_proxy_bands": (
        {"bands": [{"max_days": 90, "score": 1.00}, {"max_days": 180, "score": 0.60},
                   {"max_days": None, "score": 0.20}]},
        "Score for date proximity between the e-mail / invoice date and the BSID date.",
    ),
    "decision_thresholds": (
        {"high": 80, "medium": 40},
        ">= high + BSID match = Auto Process; >= high without match = Exception; "
        ">= medium = Manual Review; below = Manual Investigation.",
    ),
    "fast_path": (
        {"enabled": True, "exact_full_match_score": 92, "exact_amount_missing_score": 91,
         "amount_tolerance_pct": 2},
        "Exact 10-digit invoice + BSID + same currency (+ amount within tolerance) sets confidence directly.",
    ),
    "duplicate_detection": (
        {"amount_tolerance_pct": 0.01, "window_days": 7, "match_on_attachment_hash": True},
        "Same invoice, customer, amount, currency and sender domain within the window = duplicate.",
    ),
    "unreferenced_payment": (
        {"enabled": True, "amount_tolerance_pct": 0.5, "max_invoices": 6, "always_review": True},
        "Payments without invoice numbers: find open invoices that add up to the amount; always sent for review.",
    ),
    "partial_payment": (
        {"allow_discounts": False, "keep_residual_open": True},
        "Short payments: reduce the open amount by what was paid; the rest stays open. No discounts.",
    ),
    "ptp": (
        {"grace_days": 3, "escalate_after_days": 2},
        "A promise is broken if not paid within grace_days after the promised date; then escalated.",
    ),
    "sla": (
        {"pending_review_business_days": 2, "exception_business_days": 1},
        "Time allowed before an open row is escalated to the AR Supervisor.",
    ),
}
