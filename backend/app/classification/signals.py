"""Find the classification signals in an e-mail.

Each keyword pattern counts at most once per e-mail (where it is found first: subject, body,
attachment name, attachment text), so a long attachment that repeats a phrase does not outweigh
the body. Structural signals: invoice references, amounts, payment references, dates after the
business date, sender known in ADR6.
"""
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

from app.classification import lexicons
from app.classification.inputs import ClassifierInput

_GERMAN = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"})


def fold(text: str) -> str:
    """Lower case, umlauts written out, Latin accents removed, full-width -> normal, one space."""
    text = unicodedata.normalize("NFKC", text or "").translate(_GERMAN).lower()
    out = []
    for ch in text:
        if ord(ch) < 0x0250:  # Latin only - Japanese kana must keep their marks
            ch = "".join(c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c))
        out.append(ch)
    return re.sub(r"[ \t\r\f\v]+", " ", "".join(out))


def _compile(entries):
    return [(name, re.compile(rx), w) for name, rx, w in entries]


REMITTANCE = _compile(lexicons.REMITTANCE)
PTP = _compile(lexicons.PTP)
OUT_OF_SCOPE = {cat: _compile(e) for cat, e in lexicons.OUT_OF_SCOPE.items()}
ATTACHMENT_NAMES = {cls: _compile(e) for cls, e in lexicons.ATTACHMENT_NAMES.items()}
PAYMENT_REFERENCE = re.compile(lexicons.PAYMENT_REFERENCE)
INVOICE_REFERENCE = re.compile(lexicons.INVOICE_REFERENCE)
AMOUNT = re.compile(lexicons.AMOUNT)

# --------------------------------------------------------------------------- dates
_MONTHS = {
    "jan": 1, "feb": 2, "fev": 2, "mar": 3, "maer": 3, "apr": 4, "avr": 4, "abr": 4, "may": 5, "mai": 5, "mei": 5,
    "jun": 6, "juin": 6, "jul": 7, "juil": 7, "aug": 8, "aou": 8, "ago": 8, "sep": 9, "set": 9, "oct": 10, "okt": 10,
    "out": 10, "nov": 11, "dec": 12, "dez": 12, "dic": 12,
}
_MONTH_RX = r"(jan\w*|feb\w*|fev\w*|mar\w*|maer\w*|apr\w*|avr\w*|abr\w*|may|mai|jun\w*|juin\w*|jul\w*|juil\w*|aug\w*|aou\w*|ago\w*|sep\w*|set\w*|oct\w*|okt\w*|out\w*|nov\w*|dec\w*|dez\w*|dic\w*)"
_DATE_PATTERNS = [
    ("ymd", re.compile(r"\b(20\d\d)[-/.](\d{1,2})[-/.](\d{1,2})\b")),
    ("dmy?", re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](20\d\d)\b")),
    ("d mon y", re.compile(r"\b(\d{1,2})\.?[\s-]+(?:de\s+)?" + _MONTH_RX + r"\.?[\s-]+(?:de\s+)?(20\d\d)\b")),
    ("mon d y", re.compile(r"\b" + _MONTH_RX + r"\.?\s+(\d{1,2}),?\s+(20\d\d)\b")),
    ("jp", re.compile(r"(20\d\d)年(\d{1,2})月(\d{1,2})日")),
]


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _month(word: str) -> int | None:
    for key in sorted(_MONTHS, key=len, reverse=True):
        if word.startswith(key):
            return _MONTHS[key]
    return None


def find_dates(folded: str) -> list[tuple[str, list[date]]]:
    """Every date found -> (text, possible readings). 03/11/2026 has two readings (day-first, US)."""
    found = []
    for kind, rx in _DATE_PATTERNS:
        for m in rx.finditer(folded):
            g = m.groups()
            if kind in ("ymd", "jp"):
                readings = [_safe_date(int(g[0]), int(g[1]), int(g[2]))]
            elif kind == "dmy?":
                a, b, y = int(g[0]), int(g[1]), int(g[2])
                readings = [_safe_date(y, b, a), _safe_date(y, a, b)]
            elif kind == "d mon y":
                mon = _month(g[1])
                readings = [_safe_date(int(g[2]), mon, int(g[0]))] if mon else []
            else:
                mon = _month(g[0])
                readings = [_safe_date(int(g[2]), mon, int(g[1]))] if mon else []
            readings = sorted({r for r in readings if r})
            if readings:
                found.append((m.group(0), readings))
    return found


# --------------------------------------------------------------------------- signals
@dataclass
class Hit:
    cls: str          # REMITTANCE | PTP | OUT_OF_SCOPE:<CATEGORY> | EVIDENCE
    signal: str
    where: str        # subject | body | attachment name | attachment text
    text: str
    weight: float

    def as_reason(self) -> dict:
        return {"class": self.cls, "signal": self.signal, "where": self.where, "text": self.text[:80],
                "weight": self.weight}


@dataclass
class Signals:
    hits: list[Hit] = field(default_factory=list)
    invoice_refs: list[str] = field(default_factory=list)
    payment_refs: list[str] = field(default_factory=list)
    amounts: int = 0
    future_dates: list[str] = field(default_factory=list)
    past_dates: list[str] = field(default_factory=list)
    sender_known: bool | None = None
    has_attachments: bool = False

    def score(self, cls: str) -> float:
        return sum(h.weight for h in self.hits if h.cls == cls)

    def oos_scores(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for h in self.hits:
            if h.cls.startswith("OUT_OF_SCOPE:"):
                cat = h.cls.split(":", 1)[1]
                out[cat] = out.get(cat, 0) + h.weight
        return out


def _zones(inp: ClassifierInput) -> list[tuple[str, str]]:
    zones = [("subject", fold(inp.subject)), ("body", fold(inp.body))]
    zones += [("attachment name", re.sub(r"[_\-]+", " ", fold(d.name))) for d in inp.attachments]
    zones += [("attachment text", fold(d.text)) for d in inp.attachments if d.text]
    return zones


def _scan(zones, patterns, cls: str, hits: list[Hit], only: tuple[str, ...] | None = None) -> None:
    for name, rx, weight in patterns:
        for where, text in zones:
            if only and where not in only:
                continue
            m = rx.search(text)
            if m:
                hits.append(Hit(cls, name, where, m.group(0).strip(), float(weight)))
                break


def extract_signals(inp: ClassifierInput) -> Signals:
    zones = _zones(inp)
    text_zones = ("subject", "body", "attachment text")
    s =Signals(sender_known=inp.sender_known, has_attachments=bool(inp.attachments))

    _scan(zones, REMITTANCE, "REMITTANCE", s.hits, text_zones)
    _scan(zones, PTP, "PTP", s.hits, text_zones)
    for cat, patterns in OUT_OF_SCOPE.items():
        _scan(zones, patterns, f"OUT_OF_SCOPE:{cat}", s.hits, text_zones)
    for cls, patterns in ATTACHMENT_NAMES.items():
        target = cls if cls in ("REMITTANCE", "PTP") else f"OUT_OF_SCOPE:{cls}"
        _scan(zones, patterns, target, s.hits, ("attachment name",))

    raw = inp.all_text()
    s.invoice_refs = sorted(set(INVOICE_REFERENCE.findall(raw)))
    s.payment_refs = sorted(set(PAYMENT_REFERENCE.findall(raw)))
    s.amounts = len(AMOUNT.findall(raw))
    if inp.business_date:
        for text, readings in find_dates(fold(raw)):
            if all(r > inp.business_date for r in readings):
                s.future_dates.append(text)
            elif all(r <= inp.business_date for r in readings):
                s.past_dates.append(text)
    return s
