"""Invoice lines from one source: tables (header-aware), column-aligned text lines, and prose.

Each line keeps: the invoice number as written + normalised, amount paid (net), gross, deduction +
reason, line currency (the invoice's) and payment currency, credit-note flag, invoice date, promise
date (+ wording), instalment number, and evidence for every value. Nothing is converted.
"""
import difflib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.classification.lexicons import PTP as PTP_PHRASES
from app.extraction.amounts import Amount, currency_in, find_amounts, parse_number, to_iso
from app.extraction.dates import find_dates, parse_date
from app.extraction.documents import Source, join_wrapped, sentences
from app.extraction.refs import clean_ref, find_column_ref, find_refs, is_credit_note_ref, normalise_ref
from app.classification.signals import fold

_PTP_RX = [re.compile(rx) for _, rx, w in PTP_PHRASES if w >= 2]
CREDIT_WORDS = re.compile(r"credit\s*note|gutschrift|\bavoir\b|nota\s+de\s+cr[eé]dito|nota\s+de\s+credito|返品|赤伝|\bCN\b", re.I)


@dataclass
class Line:
    ref_raw: str
    ref_norm: str
    source: Source
    method: str                         # table | text_line | prose | mention | instalment
    amount: Decimal | None = None       # net amount paid / promised
    gross: Decimal | None = None
    deduction: Decimal | None = None
    deduction_reason: str | None = None
    line_currency: str | None = None    # the invoice's currency
    payment_currency: str | None = None # the currency it was paid in
    credit_note: bool = False
    invoice_date: date | None = None
    promise_date: date | None = None
    promise_text: str | None = None
    instalment_no: int | None = None
    line_type: str | None = None        # REMITTANCE | PTP
    in_ptp_sentence: bool = False
    evidence: dict = field(default_factory=dict)

    @property
    def priority(self) -> int:
        return {"table": 0, "instalment": 0, "text_line": 1, "prose": 2, "mention": 3}[self.method]


def nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def is_ptp_text(text: str) -> bool:
    f = fold(text)
    return any(rx.search(f) for rx in _PTP_RX)


# --------------------------------------------------------------------------- table columns
ROLE_WORDS = {
    "ref": ["invoice no", "invoice number", "invoice #", "invoice", "inv no", "inv. no", "document no", "doc no",
            "document", "your reference", "reference", "rechnungs-nr", "rechnungsnr", "rechnungsnummer", "rechnung",
            "beleg-nr", "belegnummer", "n° facture", "no facture", "numero de facture", "facture", "nº factura",
            "n.º factura", "no. factura", "numero de factura", "factura", "nº fatura", "n° fatura", "no fatura",
            "numero da fatura", "fatura", "請求書番号", "請求書no", "請求番号", "請求書"],
    "paid": ["amount paid", "paid amount", "net paid", "net amount", "net", "paid", "payment amount", "amount",
             "zahlbetrag", "gezahlt", "bezahlt", "betrag", "montant regle", "montant paye", "montant", "importe pagado",
             "importe", "valor pago", "valor", "金額", "支払金額", "振込金額", "お支払金額", "お支払い金額"],
    "gross": ["invoice amount", "gross amount", "gross", "original amount", "rechnungsbetrag", "bruttobetrag",
              "montant facture", "montant de la facture", "importe factura", "importe de la factura", "valor da fatura",
              "valor fatura", "請求金額"],
    "deduction": ["tds", "deduction", "deductions", "withholding tax", "withholding", "wht", "bank charges", "charges",
                  "abzug", "abzuege", "skonto", "retenue", "frais bancaires", "frais", "retencion", "retencao",
                  "descuento", "desconto", "差引", "手数料", "源泉"],
    "currency": ["currency", "curr", "ccy", "waehrung", "devise", "moneda", "moeda", "通貨"],
    "date": ["invoice date", "inv date", "date", "rechnungsdatum", "datum", "date facture", "date de facture",
             "fecha factura", "fecha de factura", "fecha", "data da fatura", "data fatura", "data", "請求日"],
}
_ROLE_INDEX = sorted(((kw, role) for role, kws in ROLE_WORDS.items() for kw in kws), key=lambda x: -len(x[0]))


def cell_role(cell: str) -> str | None:
    f = re.sub(r"[.:#]+$", "", fold(nfkc(cell)).strip())
    if not f or len(f) > 40:
        return None
    for kw, role in _ROLE_INDEX:
        if f == kw:
            return role
    # the whole cell first (OCR typos: "involcg no.", "amount pald", "involce amount"), then keywords inside it
    ratio = lambda kw: difflib.SequenceMatcher(None, f, kw).ratio()
    best = max(_ROLE_INDEX, key=lambda kr: ratio(kr[0]))
    if ratio(best[0]) >= 0.85:
        return best[1]
    for kw, role in _ROLE_INDEX:
        if len(kw) > 3 and kw in f:
            return role
    return best[1] if ratio(best[0]) >= 0.78 else None


def _header(rows: list[list[str]]) -> tuple[int, dict[str, int]] | None:
    for i, row in enumerate(rows[:30]):
        roles: dict[str, int] = {}
        for j, cell in enumerate(row):
            r = cell_role(cell)
            if r and r not in roles:
                roles[r] = j
        if "ref" in roles and len(roles) >= 2:
            return i, roles
    return None


_SEGMENT = re.compile(r"\S+(?: \S+)*")  # cells in a column-aligned line are separated by 2+ spaces


def aligned_tables(text: str) -> list[dict]:
    """Tables in column-aligned text (text PDFs, OCR): a header line with an invoice-number column,
    then each value goes to the header column it sits under. Blank lines between rows are allowed."""
    lines = nfkc(text).splitlines()
    out, i = [], 0
    while i < len(lines):
        segs = [(m.start(), m.end(), m.group(0)) for m in _SEGMENT.finditer(lines[i])]
        roles = [cell_role(t) for _, _, t in segs]
        if len(segs) < 2 or "ref" not in roles or len(set(r for r in roles if r)) < 2:
            i += 1
            continue
        header = segs
        rows, misses, j = [[t for _, _, t in header]], 0, i + 1
        while j < len(lines) and misses < 4:
            dsegs = [(m.start(), m.end(), m.group(0)) for m in _SEGMENT.finditer(lines[j])]
            j += 1
            if not dsegs:
                continue
            droles = [cell_role(t) for _, _, t in dsegs]
            if "ref" in droles and len(set(r for r in droles if r)) >= 2:
                j -= 1
                break  # the next table's header
            cells = [""] * len(header)
            for a, b, t in dsegs:
                overlap = [max(0, min(b, hb) - max(a, ha)) for ha, hb, _ in header]
                k = max(range(len(header)), key=lambda n: (overlap[n], -abs((a + b) / 2 - (header[n][0] + header[n][1]) / 2)))
                cells[k] = (cells[k] + " " + t).strip()
            rows.append(cells)
            has_ref = bool(find_refs(" ".join(cells), weak_ok=True)) or bool(cells[0] and re.search(r"\d", cells[0]))
            misses = 0 if has_ref else misses + 1
            if re.search(r"total|gesamt|summe|合計", fold(" ".join(cells))):
                break
        out.append({"rows": rows, "page": None, "from_text": True})
        i = j
    return out


def _cell_amount(cell: str, currency: str | None) -> Amount | None:
    found = find_amounts(nfkc(cell), currency)
    return found[-1] if found else None


def _signed(a: Amount | None) -> Decimal | None:
    return None if a is None else (-a.value if a.negative else a.value)


def lines_from_tables(src: Source, doc_currency: str | None, base: date | None, prefer_us: bool) -> tuple[list[Line], list[Amount]]:
    """Lines from every table with an invoice-number column; also returns the "Total" amounts seen."""
    out, totals = [], []
    tables = src.all_tables()
    if src.kind in ("pdf_text", "ocr", "body", "other"):
        tables = aligned_tables(src.text) + tables
    seen_refs: set[str] = set()
    for table in tables:
        rows = [[nfkc(c) for c in r] for r in table.get("rows", [])]
        h = _header(rows)
        if not h:
            continue
        start, cols = h
        for row in rows[start + 1:]:
            if not any(c.strip() for c in row):
                continue
            row_text = "  ".join(row)
            ref_cell = row[cols["ref"]] if cols["ref"] < len(row) else ""
            col_ref = find_column_ref(ref_cell) if ref_cell.strip() else None
            refs = ([col_ref] if col_ref else []) or find_refs(row_text)
            if not refs:
                if re.search(r"total|gesamt|summe|montant total|合計", fold(row_text)):
                    totals += [a for a in find_amounts(row_text, doc_currency)]
                continue
            cell = lambda role: row[cols[role]] if role in cols and cols[role] < len(row) else ""
            col_cur = to_iso(cell("currency").strip())   # a currency column = the invoice's currency
            sym_cur = currency_in(row_text)              # a symbol written in this row
            row_cur = col_cur or sym_cur or doc_currency  # used only to read the numbers (decimals)
            paid = _cell_amount(cell("paid"), row_cur)
            gross = _cell_amount(cell("gross"), row_cur)
            ded = _cell_amount(cell("deduction"), row_cur)
            if paid is None and gross is None:  # no amount columns recognised: numbers right of the reference
                rest = row_text.upper().replace(refs[0].group(0).strip(), " ", 1)
                nums = find_amounts(rest, row_cur)
                if nums:
                    paid = nums[-1]
                    gross = nums[0] if len(nums) > 1 else None
            if all(normalise_ref(clean_ref(m.group(0).strip())) in seen_refs for m in refs):
                continue  # same row already read from another table view of this source
            for k, m in enumerate(refs):
                raw = clean_ref(m.group(0).strip())
                seen_refs.add(normalise_ref(raw))
                line = Line(raw, normalise_ref(raw), src, "table")
                if k == 0:  # several numbers in one cell: amounts stay with the first
                    line.amount, line.gross, line.deduction = _signed(paid), _signed(gross), _signed(ded)
                    if ded is not None:
                        line.deduction_reason = re.sub(r"[.:]+$", "", cell_header(rows[start], cols["deduction"]))
                    # invoice currency only when written for the invoice; payment currency from the paid amount
                    line.line_currency = (gross.currency if gross and gross.currency else None) or col_cur or sym_cur
                    line.payment_currency = (paid.currency if paid and paid.currency else None) or col_cur
                    d = parse_date(cell("date"), base, prefer_us) if cell("date") else None
                    line.invoice_date = d.value if d else None
                line.credit_note = bool(is_credit_note_ref(raw) or CREDIT_WORDS.search(row_text)
                                        or (line.amount is not None and line.amount < 0))
                line.evidence = {"ref": src.locate(m.group(0)), "row": row_text[:200], "page": table.get("page")}
                if paid is not None:
                    line.evidence["amount"] = src.locate(paid.raw)
                out.append(line)
    return out, totals


def cell_header(row: list[str], j: int) -> str:
    return row[j].strip() if j < len(row) else ""


# --------------------------------------------------------------------------- text lines and prose
_REF_AMOUNT = re.compile(r"\(\s*([^()]{1,30}?\d[^()]{0,6})\s*\)")


# SWIFT MT103 field 70 / structured remittance information: /INV/UK-1043976/1338.08  (/RFB/, /ROC/ too)
_SWIFT = re.compile(r"/(?:INV|RFB|ROC)/([A-Z0-9][A-Z0-9/.-]*?[A-Z0-9])(?:/(-?\d[\d.,]*))?(?=\s|$|/[A-Z]{3}/)", re.I)


def _join_wrapped_fields(text: str) -> str:
    """Banks wrap field 70 at a fixed width: '/INV/A/1.00/INV/JP' + '-26-002880/181632' -> one line."""
    out: list[str] = []
    for ln in text.splitlines():
        s = ln.strip()
        if out and out[-1].startswith("/") and s and " " not in s and re.fullmatch(r"[A-Z0-9/.,-]+", s, re.I):
            out[-1] += s
        else:
            out.append(s if s.startswith("/") else ln)
    return "\n".join(out)


def lines_from_text(src: Source, doc_currency: str | None, base: date | None, prefer_us: bool) -> list[Line]:
    text = nfkc(src.text)
    out: list[Line] = []
    for m in _SWIFT.finditer(_join_wrapped_fields(text)):
        raw = clean_ref(m.group(1))
        line = Line(raw, normalise_ref(raw), src, "table")  # structured field: as reliable as a table row
        if m.group(2):
            line.amount = parse_number(m.group(2).lstrip("-"), doc_currency)
            if line.amount is not None and m.group(2).startswith("-"):
                line.amount = -line.amount
        line.credit_note = is_credit_note_ref(raw) or bool(line.amount is not None and line.amount < 0)
        line.evidence = {"ref": src.locate(m.group(0)), "row": m.group(0), "note": "structured remittance information"}
        out.append(line)
    for start, sent in sentences(join_wrapped(text)):
        refs = find_refs(sent)
        if not refs:
            continue
        ptp = is_ptp_text(sent)
        dates = find_dates(sent, base, prefer_us)
        promise = next((d for d in dates if base is None or d.value >= (base.replace(day=1))), None) if ptp else None
        amounts = find_amounts(_mask_refs(sent, refs), doc_currency)
        aligned = bool(re.search(r"\S\s{2,}\S", sent)) and len(refs) == 1
        for m in refs:
            raw = clean_ref(m.group(0))
            line = Line(raw, normalise_ref(raw), src, "mention", in_ptp_sentence=ptp)
            after = sent[m.end():m.end() + 40]
            pm = _REF_AMOUNT.match(after.lstrip()) if after.lstrip().startswith("(") else None
            own = find_amounts(pm.group(1), doc_currency) if pm else []
            if own:                                      # "JP-26-002358 (AUD 951.50)"
                line.method, line.amount = "prose", _signed(own[-1])
                line.payment_currency = own[-1].currency
            elif aligned and amounts:                    # "MUM/2627/04212   03-04-2026   7,56,217.16"
                line.method = "text_line"
                line.amount = _signed(amounts[-1])
                line.gross = _signed(amounts[0]) if len(amounts) > 1 else None
                line.payment_currency = amounts[-1].currency
            elif len(refs) == 1 and len(amounts) == 1:  # "Payment of KWD 138.000 for MUM/2627/05088 is ..."
                line.method, line.amount = "prose", _signed(amounts[0])
                line.payment_currency = amounts[0].currency
            if line.method == "text_line":  # a currency written in the row belongs to the invoice too
                line.line_currency = line.payment_currency
            if promise:
                line.promise_date, line.promise_text = promise.value, promise.raw
            line.credit_note = bool(is_credit_note_ref(raw) or (line.amount is not None and line.amount < 0))
            line.evidence = {"ref": src.locate(m.group(0)), "sentence": sent.strip()[:240]}
            out.append(line)
    return out


def _mask_refs(text: str, refs: list[re.Match]) -> str:
    up = text
    for m in refs:
        up = up[:m.start()] + " " * (m.end() - m.start()) + up[m.end():]
    return up


_INSTALMENT = re.compile(r"^\s*[-•*–]?\s*(.{6,30}?)\s*[:：]\s*(.+?)\s*$")


def instalments(src: Source, doc_currency: str | None, base: date | None, prefer_us: bool) -> list[tuple[date, Amount, str]]:
    """'- 2026-11-10: $5,206.25' / '- 16. November 2026: 2.012,34 EUR' lines (P08)."""
    out = []
    for ln in nfkc(src.text).splitlines():
        m = _INSTALMENT.match(ln)
        if not m:
            continue
        d = parse_date(m.group(1), base, prefer_us)
        a = find_amounts(m.group(2), doc_currency)
        if d and d.kind != "relative" and a and len(a) == 1:
            out.append((d.value, a[0], ln.strip()))
    return out
