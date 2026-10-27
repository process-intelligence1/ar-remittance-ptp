"""The e-mail body as a document: text + tables in the same structure as attachments.

- HTML bodies: <table>s are read cell by cell (source "html"); the text keeps one line per row.
- Plain-text bodies: column-aligned blocks are recognised as tables (source "text") - this is
  what body-only remittances such as R02, R13, R22 look like.
"""
from app.documents.common import detect_language
from app.documents.tables import find_html_tables, find_text_tables


def parse_body(text: str, html: str | None = None) -> tuple[dict, str | None]:
    """(layout, language) for a body. `text` is the clean body (quoted replies removed)."""
    tables: list[dict] = []
    if html:
        tables += [{"page": None, "source": "html", "rows": rows} for rows in find_html_tables(html)]
    if not tables:  # plain text, or HTML without real <table>s
        tables += [{"page": None, "source": "text", "rows": t["rows"], "first_line": t["first_line"]}
                   for t in find_text_tables(text)]
    return {"pages": [], "tables": tables, "format": "html" if html else "text"}, detect_language(text)
