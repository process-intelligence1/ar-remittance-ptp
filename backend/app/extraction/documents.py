"""What extraction reads: the e-mail's sources (clean body + each parsed attachment) in one shape.

A source has its text, its tables (from M02, plus column-aligned blocks found in the text) and word
boxes (for evidence highlighting). `kind` is used for the hit-rate per source in the report:
body | pdf_text | ocr | xlsx | docx | csv | other
"""
import re
from dataclasses import dataclass, field
from datetime import date

from app.documents.tables import find_text_tables
from app.classification.signals import fold

KIND_BY_METHOD = {"text": "pdf_text", "ocr": "ocr", "mixed": "ocr", "spreadsheet": "xlsx", "docx": "docx",
                  "csv": "csv", "html": "other", "plain": "other"}
SOURCE_LABELS = {"body": "Body", "pdf_text": "Text PDF", "ocr": "OCR (scan / image)", "xlsx": "Excel",
                 "docx": "Word", "csv": "CSV", "other": "Other"}


@dataclass
class Source:
    key: str                         # "body" or "att:<id>" / "att:<filename>"
    kind: str                        # body | pdf_text | ocr | xlsx | docx | csv | other
    name: str                        # "body" or the file name
    text: str
    tables: list[dict] = field(default_factory=list)   # [{"rows": [[cell, ...]], "page": n | None}]
    pages: list[dict] = field(default_factory=list)    # M02 pages with "words": [[text, x0, y0, x1, y1, conf]]
    attachment_id: int | None = None

    def all_tables(self) -> list[dict]:
        """M02 tables plus column-aligned blocks in the text (text PDFs have no detected tables)."""
        out = list(self.tables)
        if self.kind in ("pdf_text", "ocr", "body", "other"):
            seen = {tuple(map(tuple, t["rows"])) for t in out}
            for t in find_text_tables(self.text):
                if tuple(map(tuple, t["rows"])) not in seen:
                    out.append({"rows": t["rows"], "page": None, "from_text": True})
        return out

    def locate(self, raw: str) -> dict:
        """Evidence for a value: where it is (page + box) when the words are known."""
        ev: dict = {"source": self.key, "file": None if self.kind == "body" else self.name, "kind": self.kind,
                    "text": raw}
        target = re.sub(r"\s+", "", raw or "").lower()
        if not target:
            return ev
        for page in self.pages:
            words = page.get("words") or []
            for i, w in enumerate(words):
                joined = ""
                for j in range(i, min(i + 6, len(words))):
                    joined += str(words[j][0]).lower()
                    if joined == target:
                        xs = [words[k][1] for k in range(i, j + 1)] + [words[k][3] for k in range(i, j + 1)]
                        ys = [words[k][2] for k in range(i, j + 1)] + [words[k][4] for k in range(i, j + 1)]
                        ev.update(page=page.get("page"), bbox=[min(xs), min(ys), max(xs), max(ys)])
                        return ev
                    if not target.startswith(joined):
                        break
        return ev


@dataclass
class ExtractionInput:
    subject: str
    sources: list[Source]
    sender_email: str | None = None
    email_date: date | None = None        # base for relative promise dates
    business_date: date | None = None
    label: str | None = None              # M03 label
    contains_remittance: bool = True
    contains_ptp: bool = False
    currency_decimals: dict[str, int] = field(default_factory=dict)

    @property
    def sender_domain(self) -> str | None:
        return self.sender_email.rsplit("@", 1)[1].lower() if self.sender_email and "@" in self.sender_email else None

    @property
    def prefer_us_dates(self) -> bool:
        """mm/dd/yyyy for American senders (US$ amounts or .com/.us domains with US-style text)."""
        text = " ".join(s.text for s in self.sources)[:20000]
        us_money = bool(re.search(r"US\$|\bUSD\b|\$\s?\d", text))
        return us_money and (self.sender_domain or "").endswith((".com", ".us")) and not re.search(
            r"\b(?:GmbH|SARL|SAS|Ltda|S\.L\.|Pvt|plc)\b", text)


def body_source(text: str, layout: dict | None) -> Source:
    tables = [{"rows": t["rows"], "page": None} for t in (layout or {}).get("tables", [])]
    return Source("body", "body", "body", text or "", tables)


def attachment_source(key: str, filename: str, parse_method: str | None, text: str | None, layout: dict | None,
                      attachment_id: int | None = None) -> Source:
    layout = layout or {}
    kind = KIND_BY_METHOD.get(parse_method or "", "other")
    if kind == "other" and filename.lower().endswith(".csv"):
        kind = "csv"
    return Source(key, kind, filename, text or "", [{"rows": t.get("rows", []), "page": t.get("page")}
                                                    for t in layout.get("tables", [])],
                  layout.get("pages", []), attachment_id)


_ABBREV = {"rs", "nr", "no", "inv", "ref", "co", "ltd", "pvt", "inc", "dr", "st", "vs", "approx", "ca", "z.b", "bzw", "n°", "nº"}


def sentences(text: str) -> list[tuple[int, str]]:
    """(start offset, sentence): split at line breaks and at . ! ? followed by space + capital/digit -
    but not after an ordinal day ("13. November"), an initial or an abbreviation ("Rs.", "Nr.", "Inv.")."""
    cuts = []
    for m in re.finditer(r"[.!?。]\s+(?=[A-ZÄÖÜÉ0-9請「])", text):
        word = re.search(r"(\S+)$", text[:m.start()])
        w = (word.group(1) if word else "").lower().rstrip(".")
        if re.fullmatch(r"\d{1,2}|[a-z]", w) or w in _ABBREV:
            continue
        cuts.append(m.end())
    out, pos = [], 0
    for cut in cuts + [len(text)]:
        chunk_start = pos
        for line in text[pos:cut].split("\n"):
            if line.strip():
                out.append((chunk_start, line))
            chunk_start += len(line) + 1
        pos = cut
    return out


def join_wrapped(text: str) -> str:
    """PDFs wrap prose at a fixed width ("... for MUM/2526/04127," + "MUM/2627/04478 is scheduled ..."):
    join such lines so a sentence is read whole. Column-aligned lines (2+ spaces) stay as they are."""
    out: list[str] = []
    for ln in text.split("\n"):
        prev = out[-1] if out else ""
        if (prev.strip() and ln.strip() and not re.search(r"\S\s{2,}\S", prev) and not re.search(r"\S\s{2,}\S", ln)
                and not re.search(r"[.:;!?。]\s*$", prev) and not re.match(r"\s*[-•*–]\s", ln)):
            out[-1] = prev.rstrip() + " " + ln.strip()
        else:
            out.append(ln)
    return "\n".join(out)


def folded(text: str) -> str:
    return fold(text)
