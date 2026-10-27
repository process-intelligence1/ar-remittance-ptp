"""M03 - e-mail classification: REMITTANCE / PTP / OUT_OF_SCOPE.

- inputs.py    what the classifier looks at (subject, body, attachment names + text, sender)
- lexicons.py  multilingual keyword lists (EN/DE/FR/ES/PT/JA)
- signals.py   finds the signals (keywords, attachment names, amounts, invoice refs, dates)
- rules.py     turns signals into a label, flags, out-of-scope category, confidence, reasons
- model.py     small TF-IDF + logistic regression model for cases the rules are unsure about
- classifier.py  rules first, then the model
- service.py   classifies a stored e-mail and saves ar.email_classification
- samples.py   the sample folders as classifier inputs + the expected answer (for training/evaluation)
"""
