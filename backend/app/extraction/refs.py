"""Invoice numbers and other references.

normalise_ref() is THE normalisation used on both sides of invoice matching (extracted number and
BSID XBLNR / BELNR / VBELN): upper case; spaces and - / . removed; leading zeros removed.

Invoice-number shapes come from BSID (4,840 open items):
  8 digits starting 90/91 (90031237)   AAA/9999/99999 (MUM/2627/04212)   AA-9999999 (UK-1043617, CN-...)
  AA-99-999999 (JP-26-002330)   AA9999-99999 (FA2026-09168)   AAA-999999 (SRV-100354)   AA99999999 (SI12600424)
  AA-999999 (DP-126005)   10 digits: 00..., or BELNR 90/18/17/14/15... (accepted only next to a label / in a column)
Written prefixes such as "Inv#", "INV-", "No." are not part of the number.
"""
import re

# strong shapes: safe to pick up anywhere in a text
_STRONG = (r"[A-Z]{3}/\d{4}/\d{5}|[A-Z]{2}-\d{2}-\d{6}|[A-Z]{2}\d{4}-\d{5}|"
           r"(?:UK|CN|DP|DG|DR)-\d{6,7}|SRV-\d{6}|SI\d{8}|9[01]\d{6}")
# 10-digit numbers: also bank accounts, phone numbers... only in an invoice column or after an invoice word
_WEAK = r"00\d{8}|(?:90|18|17|14|15)\d{8}"
STRONG_REF = re.compile(rf"(?<![A-Z0-9/-])(?:{_STRONG})(?![0-9/-]?\d)")
ANY_REF = re.compile(rf"(?<![A-Z0-9/-])(?:{_STRONG}|{_WEAK})(?![0-9/-]?\d)")
_PREFIX_GLUE = re.compile(r"(?<=\bINV)[-#:]|(?<=\bINVOICE)[-#:]")
PREFIX = re.compile(r"^(?:INV(?:OICE)?\s*(?:NO\.?|NR\.?|#)?\s*[#:.-]?\s*|NO\.?\s*|#\s*)", re.I)

# payment / remittance references (not invoice numbers)
PAYMENT_REF = re.compile(r"(?<![A-Z0-9])(PAY\d{5,}|ZA-\d{4,}|PV\d{5,}|RA-20\d\d-\d{3,}|TRF\d{6,}|E2E-\d{6,}|"
                         r"UTR[A-Z0-9]{8,}|ACH\d{6,}|FT\d{8,}|\d{4}/\d{3}|\d{4}-\d{3})(?![A-Z0-9])")
REMITTANCE_REF = re.compile(r"(?<![A-Z0-9])(REM-[A-Z0-9-]{3,})", re.I)
CREDIT_NOTE_PREFIX = ("CN",)


def normalise_ref(value: str | None) -> str | None:
    """Upper case; spaces and - / . removed; leading zeros removed. Same rule for both sides of matching."""
    if not value:
        return None
    v = re.sub(r"[\s\-/.]", "", value.upper())
    v = v.lstrip("0")
    return v or None


def clean_ref(raw: str) -> str:
    """The number as written, without a leading "Inv#" / "INV-" / "No." label."""
    return PREFIX.sub("", raw.strip()).strip()


def find_refs(text: str, weak_ok: bool = False) -> list[re.Match]:
    """Invoice numbers in a text. weak_ok: also 10-digit numbers (inside an invoice column / after a label)."""
    up = _PREFIX_GLUE.sub(" ", text.upper())  # "INV-JP-26-002586" -> "INV JP-26-002586" (same length)
    return list((ANY_REF if weak_ok else STRONG_REF).finditer(up))


# a loose token for an invoice-number COLUMN only: as written, even when it fits no BSID shape
# (e.g. "MUM/2627/0500" with a digit missing) - matching (M05) then says NONE / NEAR
LOOSE_REF = re.compile(r"(?<![A-Z0-9])((?=[A-Z0-9/-]*\d)[A-Z]{0,4}[A-Z0-9]*(?:[/-][A-Z0-9]+)*)(?![A-Z0-9])")


def find_column_ref(cell: str) -> re.Match | None:
    """The invoice number in an invoice-number cell (strong shape first, else the longest token)."""
    strong = find_refs(cell, weak_ok=True)
    if strong:
        return strong[0]
    up = _PREFIX_GLUE.sub(" ", PREFIX.sub(lambda m: " " * len(m.group(0)), cell.upper()))
    cands = [m for m in LOOSE_REF.finditer(up) if len(re.sub(r"[/-]", "", m.group(1))) >= 6
             and sum(ch.isdigit() for ch in m.group(1)) >= 4 and not _not_an_invoice(m.group(1))]
    return max(cands, key=lambda m: len(m.group(1)), default=None)


def is_credit_note_ref(ref: str) -> bool:
    return ref.upper().startswith(CREDIT_NOTE_PREFIX)


# --------------------------------------------------------------------------- IBAN / accounts
IBAN = re.compile(r"\b([A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){2,7}(?:\s?[A-Z0-9]{1,4})?)\b")


def valid_iban(value: str) -> bool:
    """ISO 13616 check digits (mod 97)."""
    v = re.sub(r"\s", "", value.upper())
    if not (15 <= len(v) <= 34) or not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]+", v):
        return False
    digits = "".join(str(int(c, 36)) for c in v[4:] + v[:4])
    return int(digits) % 97 == 1


_DATE_LIKE = re.compile(r"\d{1,4}[-/.](?:\d{1,2}|[A-Z]{3,9})[-/.]\d{2,4}")


def _not_an_invoice(token: str) -> bool:
    """Payment references and dates that sit in an invoice-number column of a label/value table."""
    return bool(PAYMENT_REF.fullmatch(token) or _DATE_LIKE.fullmatch(token) or IBAN.fullmatch(token))
