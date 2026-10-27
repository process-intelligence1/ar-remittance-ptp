"""M04 - extraction: a structured header + one line per invoice from body and attachments.

- refs.py      invoice-number shapes (from BSID), the shared normalisation, payment/other references
- amounts.py   locale-aware amounts, currencies, negative/credit formats
- dates.py     dates in EN/DE/FR/ES/PT/JA (incl. Japanese eras) and relative promise dates
- documents.py the e-mail's sources (body + attachments) with rows, lines and word boxes
- lines.py     invoice lines from tables, column-aligned text and prose (incl. promises, instalments)
- header.py    payer, references, customer number, bank account, payment date, total, FX rate
- extractor.py puts it together for one e-mail (no database)
- service.py   saves ar.extraction / ar.extraction_line for a stored e-mail
- llm.py       optional hosted-LLM fallback switch (interface only, off by default)
- samples.py   the sample folders as extraction inputs (evaluation, cached parse results)
"""
