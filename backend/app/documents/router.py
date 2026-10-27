"""Pick the right reader for a file (by content first, then extension) and run it under the
per-document deadline. One document at a time; large images are scaled down before OCR."""
import logging
import time

from app.config import get_settings
from app.documents.common import Deadline, ParseResult, detect_language, mean
from app.documents.ocr import get_engine, open_image_frames
from app.documents.tables import find_text_tables

log = logging.getLogger(__name__)

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp")
CONTAINER_EXT = (".zip",)


def kind_of(filename: str, mime: str | None, data: bytes) -> str:
    name = (filename or "").lower()
    head = data[:8]
    if head.startswith(b"%PDF") or name.endswith(".pdf"):
        return "pdf"
    if name.endswith(CONTAINER_EXT):
        return "container"
    if name.endswith((".docx", ".docm")):
        return "docx"
    if name.endswith((".xlsx", ".xlsm")):
        return "xlsx"
    if (head.startswith(b"\x89PNG") or head.startswith(b"\xff\xd8") or head[:4] in (b"II*\x00", b"MM\x00*")
            or name.endswith(IMAGE_EXT) or (mime or "").startswith("image/")):
        return "image"
    if name.endswith(".csv"):
        return "csv"
    if name.endswith((".html", ".htm")) or (mime or "") == "text/html":
        return "html"
    if name.endswith((".txt", ".text")) or (mime or "") == "text/plain":
        return "plain"
    return "unsupported"


def parse_image(data: bytes, deadline: Deadline) -> ParseResult:
    engine = get_engine()
    frames = open_image_frames(data)
    texts, pages, confs = [], [], []
    for n, frame in enumerate(frames, start=1):
        deadline.check()
        dpi = frame.info.get("dpi", (None,))[0] if isinstance(frame.info.get("dpi"), tuple) else None
        o = engine.ocr(frame, deadline, source_dpi=float(dpi) if dpi and dpi > 1 else None)
        pages.append({"page": n, "width": o.width, "height": o.height, "unit": "px", "source": "ocr",
                      "words": o.words})
        texts.append(o.text)
        if o.confidence is not None:
            confs.append(o.confidence)
        frame.close()
    tables = [{"page": i + 1, "source": "ocr", "rows": t["rows"]}
              for i, txt in enumerate(texts) for t in find_text_tables(txt)]
    return ParseResult("ocr", "\n\n".join(texts), pages, tables, page_count=len(frames), ocr_confidence=mean(confs))


def parse_document(filename: str, mime: str | None, data: bytes, timeout_s: float | None = None) -> ParseResult:
    """Read one file. Raises DocumentTimeout after the deadline; other errors propagate."""
    s = get_settings()
    deadline = Deadline(timeout_s or s.doc_timeout_s)
    kind = kind_of(filename, mime, data)
    if kind == "container":
        return ParseResult("container", status="SKIPPED", note="archive - its files are separate attachments")
    if kind == "unsupported":
        return ParseResult("unsupported", status="SKIPPED", note=f"file type not supported: {filename}")
    if kind == "html" and len(data) > s.html_max_bytes:
        return ParseResult("html", status="SKIPPED", note=f"HTML larger than {s.html_max_bytes:,} bytes")

    if kind == "pdf":
        from app.documents.pdf import parse_pdf
        result = parse_pdf(data, deadline)
    elif kind == "image":
        result = parse_image(data, deadline)
    else:
        from app.documents import office
        result = {"docx": office.parse_docx, "xlsx": office.parse_xlsx, "csv": office.parse_csv,
                  "html": office.parse_html, "plain": office.parse_plain}[kind](data)
    deadline.check()
    if result.status == "PARSED":
        result.language = detect_language(result.text)
    return result


def timed_parse(filename: str, mime: str | None, data: bytes, timeout_s: float | None = None) -> tuple[ParseResult, int]:
    start = time.perf_counter()
    r = parse_document(filename, mime, data, timeout_s)
    return r, int((time.perf_counter() - start) * 1000)
