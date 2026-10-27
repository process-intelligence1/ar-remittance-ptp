"""Invoice-number matching against BSID (replaces the prototype's "digit match length").

Both sides normalised with extraction.refs.normalise_ref (upper case; spaces and - / . removed;
leading zeros removed). Levels (ar.rule_config "invoice_match"):
  EXACT 1.00  identical after normalisation - XBLNR (primary), or BELNR / VBELN (alternates, EXACT only)
  NEAR  0.70  same length, exactly ONE character differs and that pair is a common OCR confusion
              (0/O, 1/I/L, 5/S, 8/B, 2/Z) - XBLNR only, always reviewed ("Possible OCR misread")
  NONE  0.00  anything else -> EXCEPTION "No BSID match found"
"""
from dataclasses import dataclass
from itertools import combinations

from app.matching.data import OpenItem, SapData


@dataclass(frozen=True)
class InvoiceMatch:
    item: OpenItem
    field: str        # XBLNR | BELNR | VBELN
    level: str        # EXACT | NEAR
    score: float
    detail: str | None = None   # e.g. "8 read as B"


def levels(cfg: dict) -> dict[str, dict]:
    return {lv["level"]: lv for lv in cfg["levels"]}


def confusion_pairs(cfg: dict) -> set[frozenset[str]]:
    near = levels(cfg)["NEAR"]
    pairs: set[frozenset[str]] = set()
    for group in near.get("ocr_confusions", []):
        for a, b in combinations([c.upper() for c in group], 2):
            pairs.add(frozenset((a, b)))
    return pairs


def compare(extracted: str | None, bsid: str | None, cfg: dict) -> tuple[str, str | None]:
    """Level for two NORMALISED numbers: ("EXACT" | "NEAR" | "NONE", detail)."""
    if not extracted or not bsid:
        return "NONE", None
    if extracted == bsid:
        return "EXACT", None
    if len(extracted) != len(bsid):
        return "NONE", None
    diffs = [(a, b) for a, b in zip(extracted, bsid) if a != b]
    if len(diffs) == 1 and frozenset(diffs[0]) in confusion_pairs(cfg):
        a, b = diffs[0]
        return "NEAR", f"{b} read as {a}"
    return "NONE", None


def find_matches(ref_norm: str | None, sap: SapData, cfg: dict) -> list[InvoiceMatch]:
    """Every open item the extracted number points to (EXACT on any field, NEAR on XBLNR)."""
    if not ref_norm:
        return []
    lv = levels(cfg)
    out: list[InvoiceMatch] = []
    seen: set[tuple[int, str]] = set()
    primary = cfg.get("primary_field", "XBLNR")
    fields = [primary] + [f for f in cfg.get("alternate_fields", ["BELNR", "VBELN"]) if f != primary]
    index = {"XBLNR": sap.by_xblnr, "BELNR": sap.by_belnr, "VBELN": sap.by_vbeln}
    for f in fields:
        for it in index[f].get(ref_norm, []):
            if (it.id, "EXACT") not in seen:
                out.append(InvoiceMatch(it, f, "EXACT", float(lv["EXACT"]["score"])))
                seen.add((it.id, "EXACT"))
    if out:
        return out
    # NEAR: try every one-character OCR swap of the extracted number against the PRIMARY field only
    partners: dict[str, set[str]] = {}
    for pair in confusion_pairs(cfg):
        a, b = tuple(pair)
        partners.setdefault(a, set()).add(b)
        partners.setdefault(b, set()).add(a)
    for i, ch in enumerate(ref_norm):
        for alt in partners.get(ch, ()):
            variant = ref_norm[:i] + alt + ref_norm[i + 1:]
            for it in index[primary].get(variant, []):
                if (it.id, "NEAR") not in seen:
                    out.append(InvoiceMatch(it, primary, "NEAR", float(lv["NEAR"]["score"]), f"{alt} read as {ch}"))
                    seen.add((it.id, "NEAR"))
    return out
