"""PDF: text layer with word positions (PyMuPDF) + tables (pdfplumber); OCR for pages that are
scanned (almost no text layer) or whose text layer is mostly unreadable characters.

method = text (no page needed OCR) | ocr (every page OCR) | mixed (some of each)
"""
import io

import numpy as np
import pymupdf

from app.config import get_settings
from app.documents.common import Deadline, ParseResult, box, mean, readable_ratio
from app.documents.ocr import get_engine
from app.documents.tables import find_text_tables

MIN_TEXT_CHARS = 25      # fewer characters on a page = scanned page
MIN_READABLE = 0.70      # less than 70 % readable characters = broken font mapping -> OCR


def page_needs_ocr(text: str) -> str | None:
    """Why a page must be OCR'd ('scanned' / 'unreadable text layer'), or None."""
    if len(text.strip()) < MIN_TEXT_CHARS:
        return "scanned"
    if readable_ratio(text) < MIN_READABLE:
        return "unreadable text layer"
    return None


def _pdf_tables(data: bytes, page_numbers: list[int]) -> dict[int, list[list[list[str]]]]:
    if not page_numbers:
        return {}
    import pdfplumber

    out: dict[int, list] = {}
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for n in page_numbers:
            tables = pdf.pages[n].extract_tables() or []
            out[n] = [[[(" ".join((c or "").split())) for c in row] for row in t if row and any(row)]
                      for t in tables]
    return out


def parse_pdf(data: bytes, deadline: Deadline) -> ParseResult:
    s = get_settings()
    doc = pymupdf.open(stream=data, filetype="pdf")
    if doc.needs_pass:
        return ParseResult("unsupported", status="SKIPPED", note="password-protected PDF", page_count=doc.page_count)
    n_pages = doc.page_count
    read = min(n_pages, s.pdf_max_pages)
    texts, pages, ocr_conf, ocr_reasons = [], [], [], {}
    text_pages: list[int] = []
    engine = None
    for n in range(read):
        deadline.check()
        page = doc[n]
        w, h = page.rect.width, page.rect.height
        layer = page.get_text("text", sort=True)
        reason = page_needs_ocr(layer)
        if reason is None:
            words = [[t, *box(x0, y0, x1, y1, w, h), None] for x0, y0, x1, y1, t, *_ in page.get_text("words", sort=True)]
            pages.append({"page": n + 1, "width": round(w, 1), "height": round(h, 1), "unit": "pt",
                          "source": "text", "words": words})
            texts.append(layer.strip())
            text_pages.append(n)
        else:
            engine = engine or get_engine()
            pix = page.get_pixmap(dpi=s.ocr_dpi, colorspace=pymupdf.csGRAY)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
            del pix
            o = engine.ocr(img, deadline, source_dpi=s.ocr_dpi)
            pages.append({"page": n + 1, "width": o.width, "height": o.height, "unit": "px",
                          "source": "ocr", "reason": reason, "words": o.words})
            texts.append(o.text)
            ocr_reasons[n + 1] = reason
            if o.confidence is not None:
                ocr_conf.append(o.confidence)
    doc.close()

    tables = []
    for n, page_tables in _pdf_tables(data, text_pages).items():
        tables += [{"page": n + 1, "source": "pdf", "rows": t} for t in page_tables]
    for p in pages:  # OCR pages: find column-aligned tables in the rebuilt lines
        if p["source"] == "ocr":
            tables += [{"page": p["page"], "source": "ocr", "rows": t["rows"]}
                       for t in find_text_tables(texts[p["page"] - 1])]

    method = "text" if not ocr_reasons else "ocr" if len(ocr_reasons) == read else "mixed"
    note = None
    if read < n_pages:
        note = f"only the first {read} of {n_pages} pages were read"
    if ocr_reasons:
        note = "; ".join(filter(None, [note, "OCR pages: " + ", ".join(f"{k} ({v})" for k, v in ocr_reasons.items())]))
    return ParseResult(method, "\n\n".join(texts), pages, tables, page_count=n_pages,
                       ocr_confidence=mean(ocr_conf), note=note)
