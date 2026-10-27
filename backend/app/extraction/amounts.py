"""Amounts as written in remittances, in any of the sample locales.

  15.999,58   4.600,00 EUR   11 353,25   3'797.48   ₹3,56,639.73   Rs. 32,11,468.71   ¥2,079,824
  KWD 138.000 (3 decimals)   KD 1,012.432   US$9,757.59   S$8,300.00   R$63.245,40   1,234.00-   (1,234.00)
  -1,234.00   1,234.00 CR   1.234,00 Haben
Decimal separator: the LAST of "." / "," when both occur; a single separator followed by exactly 3
digits is a thousands separator, except for 3-decimal currencies (KWD, BHD, OMR...). Currency
decimals come from sap.tcurx (CURRENCY_DECIMALS is the fallback).
Nothing is converted between currencies here.
"""
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

CURRENCY_DECIMALS = {"JPY": 0, "KRW": 0, "KWD": 3, "BHD": 3, "OMR": 3, "JOD": 3, "TND": 3}

# written forms -> ISO code (longest first when matching)
SYMBOLS = {
    "US$": "USD", "U$S": "USD", "USD": "USD", "$": "USD", "S$": "SGD", "SGD": "SGD", "A$": "AUD", "AU$": "AUD",
    "AUD": "AUD", "C$": "CAD", "CA$": "CAD", "CAD": "CAD", "R$": "BRL", "BRL": "BRL", "MX$": "MXN", "MXN": "MXN",
    "€": "EUR", "EUR": "EUR", "EURO": "EUR", "EUROS": "EUR", "£": "GBP", "GBP": "GBP", "¥": "JPY", "円": "JPY", "JPY": "JPY",
    "₹": "INR", "RS.": "INR", "RS": "INR", "INR": "INR", "₩": "KRW", "KRW": "KRW", "KD": "KWD", "KWD": "KWD",
    "CHF": "CHF", "FR.": "CHF", "SEK": "SEK", "CNY": "CNY", "RMB": "CNY", "元": "CNY", "AED": "AED",
    "DHS": "AED", "HKD": "HKD", "HK$": "HKD", "NZD": "NZD", "NZ$": "NZD", "ZAR": "ZAR", "NOK": "NOK", "DKK": "DKK",
    "PLN": "PLN", "BHD": "BHD", "OMR": "OMR", "SAR": "SAR", "QAR": "QAR", "THB": "THB", "MYR": "MYR", "IDR": "IDR",
}
_SYM = sorted(SYMBOLS, key=len, reverse=True)
_SYM_RX = "(?:" + "|".join(re.escape(s) for s in _SYM) + ")"  # grouped: boundaries apply to every symbol
# digit groups: commas/dots may group 2-3 digits (Indian lakh); spaces/apostrophes exactly 3 (so two amounts
# written side by side, '149,040 74,520', stay two amounts), then decimals
_NUM = (r"\d{1,3}(?:[.,]\d{2,3})+(?:[.,]\d{1,3})?"      # 15.999,58  3,56,639.73 (lakh: 2-digit groups)
        r"|\d{1,3}(?:[ '’  ]\d{3})+(?:[.,]\d{1,3})?"  # 11 353,25  3'797.48 (exactly 3 digits)
        r"|\d+(?:[.,]\d{1,3})?")

# an amount with optional currency before/after and sign/credit markers
AMOUNT_RX = re.compile(
    rf"(?P<neg1>\(|-|−)?\s*(?P<cur1>(?<![A-Za-z]){_SYM_RX})?\s?(?P<neg2>-|−)?\s?(?P<num>{_NUM})(?P<neg3>-)?\s?"
    rf"(?P<cur2>(?<![A-Z]){_SYM_RX}(?![A-Z]))?\s?(?P<close>\))?\s?(?P<cr>\bCR\b|\bHaben\b)?",
    re.I)


@dataclass
class Amount:
    value: Decimal
    currency: str | None
    raw: str
    negative: bool = False   # credit / minus / parentheses / CR
    start: int = 0
    end: int = 0


def to_iso(written: str | None) -> str | None:
    return SYMBOLS.get((written or "").upper().strip()) if written else None


def parse_number(text: str, currency: str | None = None) -> Decimal | None:
    """'15.999,58' -> 15999.58; '3,56,639.73' -> 356639.73; '138.000' with KWD -> 138.000."""
    s = re.sub(r"[\s'’ ]", "", text)
    if not s or not re.fullmatch(r"[\d.,]+", s) or not s[0].isdigit():
        return None
    dec = CURRENCY_DECIMALS.get((currency or "").upper(), 2)
    last_dot, last_comma = s.rfind("."), s.rfind(",")
    if last_dot >= 0 and last_comma >= 0:
        sep = "." if last_dot > last_comma else ","
    elif last_dot >= 0 or last_comma >= 0:
        sep = "." if last_dot >= 0 else ","
        tail = len(s) - s.rfind(sep) - 1
        if s.count(sep) > 1 or (tail == 3 and dec != 3) or tail == 0:
            sep = None  # thousands separator(s) only
        elif tail > 3:
            return None
    else:
        sep = None
    if sep:
        whole, frac = s[:s.rfind(sep)], s[s.rfind(sep) + 1:]
        whole = re.sub(r"[.,]", "", whole)
        number = f"{whole}.{frac}"
    else:
        number = re.sub(r"[.,]", "", s)
    try:
        return Decimal(number)
    except InvalidOperation:
        return None


def find_amounts(text: str, default_currency: str | None = None, need_currency: bool = False) -> list[Amount]:
    """Every amount-looking token. need_currency: only amounts written with a currency, or with decimals."""
    out = []
    for m in AMOUNT_RX.finditer(text):
        num = m.group("num").strip(" '’ ")
        ns, ne = m.start("num"), m.end("num")
        before, after = text[ns - 1:ns] if ns else "", text[ne:ne + 1]
        # part of an identifier or a date: UK-1043617, PAY161981, MUM/2627/04212, 19.10.2026, 2026-10-28
        if (before.isalpha() and not (m.group("cur1") or "").strip()) or before in ("/", "#") or after in ("/",)                 or (after.isalpha() and not m.group("cur2") and not m.group("cr"))                 or (m.group("neg1") == "-" and m.start() > 0 and text[m.start() - 1].isalnum())                 or re.fullmatch(r"\d{1,2}[./]\d{1,2}[./]\d{2,4}|20\d\d[./]\d{1,2}[./]\d{1,2}", num)                 or (after == "-" and text[ne + 1:ne + 2].isdigit()):
            continue
        cur = to_iso(m.group("cur1") or m.group("cur2"))
        if cur is None and re.fullmatch(r"\d{1,4}", num):
            continue  # bare small integers (quantities, days, years) are not amounts
        if re.fullmatch(r"20\d\d", num) or re.fullmatch(r"\d{1,2}[/-]\d{1,2}", num):  # a year, "28/10"
            continue
        has_decimals = bool(re.search(r"[.,]\d{1,3}$", num))
        if need_currency and not cur and not has_decimals:
            continue
        value = parse_number(num, cur or default_currency)
        if value is None:
            continue
        negative = bool(m.group("neg2") or m.group("neg3") or m.group("cr")
                        or (m.group("neg1") == "(" and m.group("close")) or m.group("neg1") in ("-", "−"))
        out.append(Amount(value, cur, m.group(0).strip(), negative, ns, ne))
    return out


def signed(a: Amount) -> Decimal:
    return -a.value if a.negative else a.value


def currency_in(text: str) -> str | None:
    """The first currency written in a text (code, symbol or word)."""
    m = re.search(rf"(?<![A-Z]){_SYM_RX}(?![A-Z])", text, re.I)
    return to_iso(m.group(0)) if m else None
