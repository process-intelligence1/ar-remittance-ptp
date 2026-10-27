"""M05 - customer identification, BSID matching, scoring, duplicates.

- data.py           in-memory views of BSID and the customer master (loaded once per run)
- invoice_match.py  EXACT / NEAR / NONE invoice-number matching (XBLNR primary, BELNR / VBELN exact only)
- customers.py      who is paying (invoice, sender address, customer no., IBAN, domain, name; KNVP payers)
- scoring.py        Knowledge Base formula, fast paths (confidence = max(fast path, formula)), decisions
- unreferenced.py   payments without invoice numbers: open invoices that add up to the amount
- duplicates.py     same invoice / customer / amount / currency / sender domain within 7 days, or same file
- matcher.py        rows for one e-mail (no database writes)
- service.py        saves ar.work_item / ar.match_candidate / ar.ptp_commitment for a stored e-mail
"""
