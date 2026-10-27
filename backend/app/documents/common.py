"""Shared pieces: the parse result, the per-document deadline, language detection, text checks."""
import time
import unicodedata
from dataclasses import dataclass, field

from langdetect import DetectorFactory, LangDetectException, detect

DetectorFactory.seed = 0  # langdetect is random by default; a fixed seed makes results repeatable


class DocumentTimeout(Exception):
    pass


class Deadline:
    """Time budget for one document. OCR calls get `remaining()` as their own timeout."""

    def __init__(self, seconds: float):
        self.seconds = seconds
        self.end = time.monotonic() + seconds

    def remaining(self) -> float:
        return self.end - time.monotonic()

    def check(self) -> None:
        if self.remaining() <= 0:
            raise DocumentTimeout(f"timeout after {self.seconds:.0f} s")


@dataclass
class ParseResult:
    method: str                       # text | ocr | mixed | docx | spreadsheet | csv | html | plain | container | unsupported
    text: str = ""
    pages: list[dict] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list)
    page_count: int | None = None
    ocr_confidence: float | None = None
    language: str | None = None
    status: str = "PARSED"            # PARSED | SKIPPED
    note: str | None = None           # e.g. why it was skipped, pages not read

    @property
    def layout(self) -> dict:
        return {"pages": self.pages, "tables": self.tables}


def box(x0: float, y0: float, x1: float, y1: float, width: float, height: float) -> list[float]:
    """Bounding box scaled to 0..1 of the page (4 decimals keeps the JSON small)."""
    return [round(x0 / width, 4), round(y0 / height, 4), round(x1 / width, 4), round(y1 / height, 4)]


def detect_language(text: str) -> str | None:
    sample = " ".join((text or "").split())[:5000]
    if sum(ch.isalpha() for ch in sample) < 20:
        return None
    try:
        return detect(sample)
    except LangDetectException:
        return None


def readable_ratio(text: str) -> float:
    """Share of characters that look like real text. A PDF text layer with a broken font mapping
    comes out as replacement characters, private-use glyphs, control codes or "(cid:123)"."""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0
    bad = text.count("(cid:") * 6  # pdf extractors write unmapped glyphs as (cid:NN)
    for c in chars:
        cat = unicodedata.category(c)
        if c == "�" or cat in ("Co", "Cc", "Cs", "Cn"):
            bad += 1
    return max(0.0, 1 - bad / len(chars))


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None
