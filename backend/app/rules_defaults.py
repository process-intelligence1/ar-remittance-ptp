"""Default business rules, taken from the prototype's Knowledge Base.

These are copied into the ar.rule_config table by `python -m scripts.seed_app`.
After that, the database copy is the one the app uses (and the AR Supervisor can
change it from the screens). Edit here only to change the factory defaults.
"""

IGNORED_SENDERS = {
    # ONLY these exact domains; each also covers its sub-domains (mail.anthropic.com, ...).
    # No address patterns: automated senders (e.g. noreply@kangaroo-erp-mail.net, sample R19-0112)
    # can send genuine remittances, so everything else is stored and classified.
    "domains": ["github.com", "google.com", "accounts.google.com", "microsoft.com", "azure.com",
                "anthropic.com", "claude.ai", "claude.com"],
}

INVOICE_MATCH = {
    "primary_field": "XBLNR",
    "alternate_fields": ["BELNR", "VBELN"],  # accepted only on an EXACT match
    # applied the same way to the extracted invoice number and to the BSID fields
    "normalisation": {"upper_case": True, "remove_spaces": True, "remove_separators": ["-", "/", "."],
                      "strip_leading_zeros": True},
    "levels": [
        {"level": "EXACT", "score": 1.00, "fast_path_eligible": True,
         "label": "Identical, or identical after normalisation"},
        {"level": "NEAR", "score": 0.70, "max_char_differences": 1,
         # compared after upper-casing, so a lower-case l counts as L
         "ocr_confusions": [["0", "O"], ["1", "I", "L"], ["5", "S"], ["8", "B"], ["2", "Z"]],
         "always_review": True, "reason": "Possible OCR misread",
         "label": "Exactly one character differs and it is a common OCR confusion"},
        {"level": "NONE", "score": 0.00, "decision": "EXCEPTION", "reason": "No BSID match found",
         "label": "No invoice-number match"},
    ],
}
CLASSIFICATION = {
    "contains_threshold": 3,       # points needed for "contains a remittance" / "contains a promise"
    "out_of_scope_threshold": 3,   # points an out-of-scope category needs to win
    "evidence_bonus": 1,           # invoice numbers / amounts / payment references found
    "known_sender_bonus": 1,       # sender is a customer contact in ADR6
    "future_date_bonus": 1,        # a date after the business date next to promise wording
    "model_below_confidence": 70,  # rules less sure than this -> the learned model is asked too
    "model_min_probability": 0.60, # the model's answer is used only when it is at least this sure
    "model_min_chars": 25,         # fewer letters/digits (subject, body, attachment text) -> nothing to read, model not asked
    "document_about_ar_categories": 3,  # remittance + promise + this many out-of-scope kinds = a document ABOUT AR
    "both_label": "PTP",           # label of an e-mail with a remittance AND a promise
    "gmail_labels": {"REMITTANCE": "AR-Remittance", "PTP": "AR-PTP", "OUT_OF_SCOPE": "AR-OutOfScope"},
}

FAST_PATH_DESCRIPTION = ("EXACT invoice match + BSID open + same currency + amount within tolerance = 92%; "
                         "EXACT + amount missing = 91% (sets confidence directly).")

DEFAULT_RULES: dict[str, tuple[dict, str]] = {
    "ignored_senders": (
        IGNORED_SENDERS,
        "System sender DOMAINS (incl. sub-domains) whose e-mails are NOT stored: only an audit entry and the "
        "Gmail label AR-Ignored. No address patterns - automated senders can send genuine remittances.",
    ),
    "classification": (
        CLASSIFICATION,
        "E-mail classification (M03): keyword points needed for remittance / promise / out-of-scope, "
        "bonuses for invoice numbers, known senders and future dates, when the learned model is asked.",
    ),
    "scoring_weights": (
        {"invoice_match": 0.35, "amount_alignment": 0.30, "sender_company": 0.10,
         "customer_name": 0.05, "date_proxy": 0.10, "normalization_max": 0.90},
        "Confidence formula weights. Raw score is divided by normalization_max to give 0-100%.",
    ),
    "invoice_match": (
        INVOICE_MATCH,
        "Invoice-number match against BSID: XBLNR primary, BELNR/VBELN exact-only alternates. "
        "EXACT 1.00, NEAR (one OCR-confusable character) 0.70 always review, NONE 0.00 = exception.",
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
         "amount_tolerance_pct": 2, "required_match_level": "EXACT"},
        FAST_PATH_DESCRIPTION,
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
