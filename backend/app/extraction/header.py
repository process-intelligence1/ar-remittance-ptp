"""Header values: payer, references, customer number, bank account / IBAN, payment date, total, FX rate.

Values are read from "label: value" pairs (2-cell table rows, "Label: value" lines, column-aligned
"Label   value" lines) with multilingual labels, then from prose ("we transferred US$9,757.59",
"Payment of $3,042.00 has been released", "Gesamtbetrag: 15.999,58 €").
"""
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.classification.signals import fold
from app.extraction.amounts import Amount, currency_in, find_amounts, parse_number
from app.extraction.dates import parse_date
from app.extraction.documents import ExtractionInput, Source, join_wrapped, sentences
from app.extraction.lines import is_ptp_text, nfkc
from app.extraction.refs import IBAN, PAYMENT_REF, REMITTANCE_REF, valid_iban

LABELS = {
    "payment_reference": r"payment\s+ref(?:erence|erenca|\.)?|zahlungsreferenz|reference\s+du\s+paiement|"
                         r"referencia\s+de(?:l)?\s+pago|referencia\s+do\s+pagamento|referencia|transaction\s+ref(?:erence)?|"
                         r"utr(?:\s+no\.?)?|振込番号|支払番号",
    "advice_number": r"advice\s+no\.?|remittance\s+no\.?|avis\s+n[°o]|aviso\s+n[°o.º]*|zahlungsavis[-\s]nr\.?",
    "payment_date": r"payment\s+date|value\s+date|zahlungsdatum|valuta|date\s+de\s+paiement|date\s+du\s+virement|"
                    r"fecha\s+de\s+pago|data\s+de\s+pagamento|data\s+do\s+pagamento|支払日|振込日",
    "promise_date": r"promised?\s+(?:payment\s+)?date|zahlungstermin|zugesagtes\s+datum|date\s+promise|"
                    r"fecha\s+comprometida|data\s+prometida|支払予定日|お支払い予定日",
    "customer_number": r"(?:your\s+)?customer\s+(?:no|nr|number|id|code|account)\.?|(?:ihre\s+)?kunden[-\s]?(?:nr|nummer)\.?|"
                       r"(?:votre\s+)?n[°o]\s*(?:de\s+)?client|numero\s+(?:de\s+)?client|(?:su\s+)?n\.?\s*[ºo°]?\s*de\s+cliente|"
                       r"numero\s+de\s+cliente|(?:seu\s+)?n[ºo°]\.?\s*(?:de\s+)?cliente|codigo\s+(?:do\s+|de\s+)?cliente|"
                       r"お客様番号|得意先(?:コード|番号)",
    "our_reference": r"our\s+ref(?:erence)?\.?|unser(?:e)?\s+(?:zeichen|referenz)|notre\s+reference|nuestra\s+referencia|"
                     r"nossa\s+referencia|当社(?:参照|番号)",
    "your_reference": r"your\s+ref(?:erence)?\.?|ihr(?:e)?\s+(?:zeichen|referenz)|votre\s+reference|su\s+referencia|"
                      r"sua\s+referencia|貴社(?:参照|番号)",
    "account": r"debit\s+account|from\s+account|payer\s+account|account\s+(?:no|number)\.?|iban|kontonummer|konto|"
               r"compte(?:\s+debite)?|cuenta|conta|口座番号",
    "total": r"total\s+(?:paid|amount|payment|regle|paye|vire|pagado|pago|transferido)|amount\s+(?:paid|transferred)\s+total|"
             r"(?:transfer\s+)?amount(?=\s{2,}(?:[a-z]{2,3}\s?)?[$€£¥₹]?\s?\d)|"
             r"gesamtbetrag|gesamtsumme|summe|montant\s+total|importe\s+total|valor\s+total|振込合計|合計",
    "fx_rate": r"(?:fx|exchange|conversion)\s+rate|wechselkurs|umrechnungskurs|taux\s+de\s+change|tipo\s+de\s+cambio|"
               r"taxa\s+de\s+cambio|為替レート",
    "ordering_customer": r"ordering\s+customer|auftraggeber|donneur\s+d'ordre|ordenante",
    "document_date": r"date|datum|fecha|data|日付|作成日|発行日",
}
# label, then the value in the same cell or the next one ("Payment reference:" | "TRF42301241")
_LABEL_RX = {k: re.compile(rf"(?:^|\s{{2,}}|\|)\s*(?:{v})\s*[:：]?\s*(?:\|\s*)?(?P<value>[^|]+?)(?=\s{{2,}}|\||$)") for k, v in LABELS.items()}
COMPANY = re.compile(r"\b(?:Ltd\.?|Limited|GmbH|AG|Inc\.?|LLC|plc|PLC|SAS|SARL|S\.A\.(?:\s+de\s+C\.V\.)?|S\.L\.|Ltda|"
                     r"Pvt\.?\s+Ltd\.?|K\.K\.|Co\.,?\s+Ltd\.?|Pte\.?\s+Ltd\.?|Pty\s+Ltd|AB|Mills|Corp\.?|Cooperative|"
                     r"株式会社|有限会社)\b")
TODAY = re.compile(r"\b(?:today|heute|heutigen|aujourd'hui|ce\s+jour|hoy|hoje|本日)\b|本日")


@dataclass
class Header:
    payer_name: str | None = None
    customer_number: str | None = None
    payer_account: str | None = None       # IBAN (check digits valid) or account number as written
    our_reference: str | None = None
    your_reference: str | None = None
    payment_reference: str | None = None
    advice_number: str | None = None
    remittance_refs: list[str] = field(default_factory=list)   # REM-...
    payment_date: date | None = None
    promise_date: date | None = None
    promise_text: str | None = None
    total: Decimal | None = None
    payment_currency: str | None = None
    fx_rate: Decimal | None = None
    evidence: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def label_values(src: Source) -> list[tuple[str, str]]:
    """(label key, value) pairs in a source, in order."""
    pairs = []
    candidates = [" | ".join(nfkc(c) for c in row) for t in src.all_tables() for row in t.get("rows", []) if len(row) >= 2]
    candidates += [nfkc(ln) for ln in src.text.splitlines()]
    for line in candidates:
        f = fold(line, keep_spaces=True)
        for key, rx in _LABEL_RX.items():
            for m in rx.finditer(f):
                value = m.group("value").strip(" :：|")
                if len(f) == len(line):
                    value = line[m.start("value"):m.end("value")].strip(" :：|")
                else:  # umlauts changed the length: find the same value, with its original case, in the line
                    hit = re.search(re.escape(value), line, re.I)
                    value = hit.group(0) if hit else value.upper()
                if value:
                    pairs.append((key, value))
    return pairs


def _first_value(pairs, key, check=None):
    for k, v in pairs:
        if k == key and (check is None or check(v)):
            return v
    return None


def extract_header(inp: ExtractionInput, doc_currency: str | None) -> Header:
    h = Header()
    base, us = inp.email_date, inp.prefer_us_dates
    # attachments first: their labelled fields are more reliable than the body's prose
    ordered = [s for s in inp.sources if s.kind != "body"] + [s for s in inp.sources if s.kind == "body"]
    document_date = None
    for src in ordered:
        pairs = label_values(src)

        def take(attr, key, check=None, convert=lambda v: v):
            if getattr(h, attr) is None:
                v = _first_value(pairs, key, check)
                if v is not None:
                    conv = convert(v)
                    if conv is not None:
                        setattr(h, attr, conv)
                        h.evidence[attr] = src.locate(v) | {"label": key}

        take("payment_reference", "payment_reference", lambda v: bool(re.search(r"[A-Z0-9]{6,}", v.upper())),
             lambda v: re.split(r"\s{2,}|\s+(?=[A-Z][a-z])", v.strip())[0][:40])
        take("advice_number", "advice_number", lambda v: bool(re.search(r"\d{3,}", v)), lambda v: v.split()[0][:40])
        take("customer_number", "customer_number", lambda v: bool(re.fullmatch(r"[A-Z0-9-]{4,12}", v.split()[0].upper())),
             lambda v: v.split()[0])
        take("our_reference", "our_reference", None, lambda v: v.split("  ")[0][:40])
        take("your_reference", "your_reference", None, lambda v: v.split("  ")[0][:40])
        take("payment_date", "payment_date", None, lambda v: (d.value if (d := parse_date(v, base, us)) else None))
        take("promise_date", "promise_date", None, lambda v: (d.value if (d := parse_date(v, base, us)) else None))
        if document_date is None:
            v = _first_value(pairs, "document_date", lambda v: parse_date(v, base, us) is not None)
            if v:
                document_date = (parse_date(v, base, us).value, src.locate(v) | {"label": "advice date"})
        if h.total is None:
            for k, v in pairs:
                if k == "total":
                    a = find_amounts(v, doc_currency)
                    if a:
                        h.total, h.payment_currency = (-a[-1].value if a[-1].negative else a[-1].value), a[-1].currency
                        h.evidence["total"] = src.locate(a[-1].raw) | {"label": "total"}
                        break
        if h.fx_rate is None:
            v = _first_value(pairs, "fx_rate", lambda v: bool(re.search(r"\d", v)))
            if v:
                m = re.search(r"\d+(?:[.,]\d+)?", v)
                h.fx_rate = Decimal(m.group(0).replace(",", ".")) if m else None  # rates: comma = decimal
                h.evidence["fx_rate"] = src.locate(v)
        if h.payer_name is None:
            v = _first_value(pairs, "ordering_customer")
            if v:
                h.payer_name, h.evidence["payer_name"] = v[:120], src.locate(v) | {"label": "ordering customer"}
        # account: IBAN anywhere (valid check digits), else a labelled account number
        if h.payer_account is None:
            for m in IBAN.finditer(nfkc(src.text).upper()):
                if valid_iban(m.group(1)):
                    h.payer_account = re.sub(r"\s", "", m.group(1))
                    h.evidence["payer_account"] = src.locate(m.group(1)) | {"label": "IBAN"}
                    break
        if h.payer_account is None:
            v = _first_value(pairs, "account", lambda v: bool(re.search(r"\d{6,}", v)))
            if v:
                h.payer_account = re.search(r"[A-Z0-9][A-Z0-9 -]{5,33}[0-9]", v.upper()).group(0).replace(" ", "")
                h.evidence["payer_account"] = src.locate(v) | {"label": "account"}
        for m in REMITTANCE_REF.finditer(nfkc(src.text)):
            if m.group(1).upper() not in h.remittance_refs:
                h.remittance_refs.append(m.group(1).upper())

    # payment reference written in the subject / file names / text without a label
    if h.payment_reference is None and h.advice_number is None:
        for text in [inp.subject] + [s.name for s in inp.sources if s.kind != "body"]:
            m = PAYMENT_REF.search(nfkc(text).upper().replace("_", " "))
            if m:
                h.advice_number = m.group(1)
                h.evidence["advice_number"] = {"source": "subject" if text == inp.subject else "file name", "text": m.group(1)}
                break

    _prose(h, inp, doc_currency)
    if h.payment_date is None and document_date and inp.contains_remittance:
        # a remittance advice carries the date it was issued = the payment date in practice
        h.payment_date, h.evidence["payment_date"] = document_date
    h.payer_name = h.payer_name or _payer_name(inp)
    h.payment_currency = h.payment_currency or doc_currency
    return h


def _prose(h: Header, inp: ExtractionInput, doc_currency: str | None) -> None:
    base, us = inp.email_date, inp.prefer_us_dates
    for src in inp.sources:
        for _, sent in sentences(join_wrapped(nfkc(src.text))):
            f = fold(sent)
            ptp = is_ptp_text(sent)
            if ptp and h.promise_date is None:
                d = next((d for d in _dates(sent, base, us)), None)
                if d:
                    h.promise_date, h.promise_text = d.value, d.raw
                    h.evidence["promise_date"] = src.locate(d.raw) | {"sentence": sent.strip()[:200]}
            paid_words = re.search(r"transferred|remitted|paid|released|ueberwiesen|veranlasst|freigegeben|angewiesen|"
                                   r"libere|liberado|vire|transferimos|"
                                   r"transferi|pagamos|efetuamos|振込|送金|payment\s+of", f)
            if not ptp and paid_words:
                if h.total is None:
                    a = [x for x in find_amounts(sent, doc_currency, need_currency=True)]
                    if len(a) == 1:
                        h.total, h.payment_currency = a[0].value, a[0].currency or h.payment_currency
                        h.evidence["total"] = src.locate(a[0].raw) | {"sentence": sent.strip()[:200]}
                if h.payment_date is None:
                    d = next((d for d in _dates(sent, base, us) if d.kind != "relative"), None)
                    if d:
                        h.payment_date = d.value
                        h.evidence["payment_date"] = src.locate(d.raw) | {"sentence": sent.strip()[:200]}
                    elif TODAY.search(f) and base:
                        h.payment_date = base
                        h.evidence["payment_date"] = {"source": src.key, "text": TODAY.search(f).group(0),
                                                      "note": "\"today\" = the e-mail date"}


def _dates(sent, base, us):
    from app.extraction.dates import find_dates
    return find_dates(sent, base, us)


def _payer_name(inp: ExtractionInput) -> str | None:
    """Letterhead (first lines of the first attachment) or the signature block of the body."""
    for src in [s for s in inp.sources if s.kind != "body"]:
        for ln in nfkc(src.text).splitlines()[:6]:
            m = re.search(rf"^\s*([A-Z0-9][\w&.,' -]{{2,80}}?{COMPANY.pattern})", ln)
            if m and not re.search(r"\b(?:to|an|a|para|bank)\b\s*:?\s*$", ln[:m.start(1)], re.I):
                return m.group(1).strip()
    body = next((s for s in inp.sources if s.kind == "body"), None)
    if body:
        for ln in reversed(nfkc(body.text).splitlines()[-12:]):
            if COMPANY.search(ln) and len(ln.strip()) <= 80 and not re.search(r"@|http", ln):
                return ln.strip()
    return None
