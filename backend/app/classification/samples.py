"""The sample folders (data/samples/emails/<CODE>/) as classifier inputs, with the expected answer.

Expected answer from the folder prefix:
    O01..O07  OUT_OF_SCOPE, category in that order (marketing ... bank notification)
    R..       REMITTANCE
    P06       PTP + remittance in the SAME e-mail ("paid these ... the rest will be paid on ...")
    P03R/P05R REMITTANCE: the payment that follows an earlier promise (P03/P05). The e-mail itself
              contains no new promise - checked by reading all six; linking it to the earlier
              promise is M10's job (PTP kept).
    P..       PTP
Attachment text is read with the M02 parser once and cached by SHA-256 in data/runtime/cache.
"""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from app.classification.inputs import ClassifierInput, Document, OOS_CATEGORIES
from app.config import get_settings
from app.gmail.parsing import clean_body, is_zip, split_address, unpack_zip
from app.gmail.sample_sender import load_sample, samples_root

CACHE_FILE = Path(get_settings().storage_local_root) / "cache" / "sample_texts.json"
OOS_BY_CODE = dict(zip(("O01", "O02", "O03", "O04", "O05", "O06", "O07"), OOS_CATEGORIES))
MIXED_SCENARIOS = ("P06",)


@dataclass
class Expected:
    label: str
    contains_remittance: bool
    contains_ptp: bool
    category: str | None = None

    @property
    def key(self) -> str:
        """Same values as Classification.key: REMITTANCE, PTP, MIXED, OUT_OF_SCOPE:<CATEGORY>."""
        if self.label == "OUT_OF_SCOPE":
            return f"OUT_OF_SCOPE:{self.category}"
        return "MIXED" if self.contains_remittance and self.contains_ptp else self.label


def expected_for(code: str) -> Expected:
    scenario = code.split("-")[0]
    if scenario.startswith("O"):
        return Expected("OUT_OF_SCOPE", False, False, OOS_BY_CODE.get(scenario, "GENERAL"))
    if scenario.startswith("R") or (scenario.startswith("P") and scenario.endswith("R")):
        return Expected("REMITTANCE", True, False)
    if scenario in MIXED_SCENARIOS:
        return Expected("PTP", True, True)
    return Expected("PTP", False, True)


def sample_codes() -> list[str]:
    return sorted(p.name for p in samples_root().iterdir() if (p / "body.txt").exists())


class TextCache:
    """SHA-256 -> extracted text, so evaluation runs don't OCR the same files again."""

    def __init__(self, path: Path = CACHE_FILE):
        self.path = path
        self.data: dict[str, str] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        self.changed = False

    def text(self, filename: str, data: bytes) -> str:
        from app.documents.router import timed_parse

        sha = hashlib.sha256(data).hexdigest()
        if sha not in self.data:
            try:
                result, _ = timed_parse(filename, None, data)
                self.data[sha] = result.text or ""
            except Exception:
                self.data[sha] = ""
            self.changed = True
        return self.data[sha]

    def save(self) -> None:
        if self.changed:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
            self.changed = False


def _documents(name: str, data: bytes, cache: TextCache) -> list[Document]:
    if is_zip(name, data):
        docs: list[Document] = []
        stack = list(unpack_zip(data))
        while stack:
            e = stack.pop(0)
            if e.children:
                stack[:0] = e.children
            else:
                docs.append(Document(e.filename, cache.text(e.filename, e.data)))
        return docs
    return [Document(name, cache.text(name, data))]


def load_input(code: str, cache: TextCache, business_date=None, known_sender=None) -> ClassifierInput:
    """known_sender: optional function(e-mail address) -> bool (ADR6 lookup)."""
    sample = load_sample(code)
    _, sender = split_address(sample.headers.get("from"))
    docs: list[Document] = []
    for p in sample.attachments:
        docs += _documents(p.name, p.read_bytes(), cache)
    return ClassifierInput(
        subject=sample.headers.get("subject", ""), body=clean_body(sample.body), attachments=docs,
        sender_email=sender, sender_known=known_sender(sender) if known_sender and sender else None,
        business_date=business_date or get_settings().business_date)


def load_corpus(codes: list[str] | None = None, known_sender=None, business_date=None,
                progress: bool = False) -> list[tuple[str, ClassifierInput, Expected]]:
    cache = TextCache()
    out = []
    for code in codes or sample_codes():
        out.append((code, load_input(code, cache, business_date, known_sender), expected_for(code)))
        if progress and cache.changed:
            print(f"  read {code}", flush=True)
    cache.save()
    return out
