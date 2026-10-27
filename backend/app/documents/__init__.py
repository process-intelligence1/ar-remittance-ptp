"""Document reading (M02): every attachment and e-mail body -> text + tables + word positions.

Entry points
  router.parse_document(filename, mime, data)   one file -> ParseResult (no database)
  body.parse_body(raw_eml, body_text)           e-mail body -> text + tables
  service.parse_email(db, email)                stored e-mail -> results saved on its rows

Layout JSON (stored in email_attachment.layout / email_message.body_layout)
  {"pages":  [{"page": 1, "width": 595.0, "height": 842.0, "unit": "pt"|"px", "source": "text"|"ocr",
               "words": [["Invoice", x0, y0, x1, y1, conf], ...]}],     # boxes scaled 0..1, conf 0-100 or null
   "tables": [{"page": 1, "source": "pdf"|"ocr"|"docx"|"xlsx"|"csv"|"html"|"text", "name": "...",
               "rows": [["Invoice No.", "Amount"], ["UK-1043514", "GBP 1,707.60"]]}]}
"""
