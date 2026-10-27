"""Sample folders as extraction inputs (evaluation / development), with M02 results cached.

Held-out split: within each scenario (R01, P03R, ...) the samples are sorted and every 3rd one
(positions 3, 6, 9, ...) is HELD OUT - the extraction rules are developed on the other two thirds
("dev") and the report shows the held-out third separately as the honest number.
"""
import hashlib
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from app.classification.classifier import classify
from app.classification.samples import load_input as load_classifier_input, TextCache
from app.config import get_settings
from app.documents.body import parse_body
from app.extraction.documents import ExtractionInput, attachment_source, body_source
from app.gmail.parsing import clean_body, is_zip, split_address, unpack_zip
from app.gmail.sample_sender import load_sample
from app.classification.samples import sample_codes

PARSE_CACHE = Path(get_settings().storage_local_root) / "cache" / "sample_parse"


def split(codes: list[str]) -> dict[str, str]:
    """code -> "dev" | "heldout"."""
    by_scenario: dict[str, list[str]] = defaultdict(list)
    for c in sorted(codes):
        by_scenario[c.split("-")[0]].append(c)
    out = {}
    for scenario_codes in by_scenario.values():
        for i, c in enumerate(scenario_codes):
            out[c] = "heldout" if i % 3 == 2 else "dev"
    return out


def _parsed(filename: str, data: bytes) -> dict:
    """M02 result for a file, cached by SHA-256 (text, tables, pages with word boxes, method)."""
    from app.documents.router import timed_parse

    sha = hashlib.sha256(data).hexdigest()
    path = PARSE_CACHE / f"{sha}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    try:
        r, _ = timed_parse(filename, None, data)
        res = {"method": r.method, "text": r.text, "tables": r.tables, "pages": r.pages}
    except Exception as exc:
        res = {"method": "failed", "text": "", "tables": [], "pages": [], "error": str(exc)}
    PARSE_CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(res, ensure_ascii=False, default=str), encoding="utf-8")
    return res


def _files(name: str, data: bytes) -> list[tuple[str, bytes]]:
    if not is_zip(name, data):
        return [(name, data)]
    out, stack = [], list(unpack_zip(data))
    while stack:
        e = stack.pop(0)
        if e.children:
            stack[:0] = e.children
        else:
            out.append((e.filename, e.data))
    return out


def load_extraction_input(code: str, text_cache: TextCache | None = None) -> ExtractionInput:
    sample = load_sample(code)
    _, sender = split_address(sample.headers.get("from"))
    body = clean_body(sample.body)
    layout, _ = parse_body(body)
    sources = [body_source(body, layout)]
    for p in sample.attachments:
        for fname, data in _files(p.name, p.read_bytes()):
            r = _parsed(fname, data)
            sources.append(attachment_source(f"att:{fname}", fname, r["method"], r["text"],
                                             {"tables": r["tables"], "pages": r["pages"]}))
    # M03 decides remittance / promise, exactly as in production
    cls = classify(load_classifier_input(code, text_cache or TextCache()))
    try:
        email_date = datetime.strptime(sample.headers.get("date", "")[:10], "%Y-%m-%d").date()
    except ValueError:
        email_date = get_settings().business_date
    return ExtractionInput(subject=sample.headers.get("subject", ""), sources=sources, sender_email=sender,
                           email_date=email_date, business_date=get_settings().business_date, label=cls.label,
                           contains_remittance=cls.contains_remittance, contains_ptp=cls.contains_ptp)


def load_all(codes: list[str] | None = None) -> list[tuple[str, ExtractionInput]]:
    cache = TextCache()
    out = [(c, load_extraction_input(c, cache)) for c in (codes or sample_codes())]
    cache.save()
    return out
