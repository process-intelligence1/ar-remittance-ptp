"""Extraction for one e-mail (no database): header + merged invoice lines + checks.

Merging: the same invoice (normalised number) found in several places becomes one line; the most
reliable source gives the values (table > aligned text line > prose > plain mention), the others
add evidence. Line type: M03's flags decide; in a mixed e-mail a line is PTP when its number sits in
a promise sentence ("the remaining invoices ... will be paid on ...").
"""
from dataclasses import dataclass, field
from decimal import Decimal

from app.extraction.amounts import currency_in
from app.extraction.documents import ExtractionInput, Source
from app.extraction.header import Header, extract_header
from app.extraction.lines import Line, instalments, lines_from_tables, lines_from_text, nfkc
from app.extraction.refs import find_refs, clean_ref, normalise_ref


@dataclass
class ExtractionResult:
    status: str                          # OK | PARTIAL (some lines without amount) | NO_LINES | SKIPPED
    header: Header
    lines: list[Line]
    doc_currency: str | None
    lines_sum: Decimal | None = None
    total_mismatch: Decimal | None = None   # total - sum of remittance lines (None = could not compare)
    warnings: list[str] = field(default_factory=list)


def document_currency(inp: ExtractionInput) -> str | None:
    for src in sorted(inp.sources, key=lambda s: s.kind == "body"):
        cur = currency_in(nfkc(src.text))
        if cur:
            return cur
    return currency_in(nfkc(inp.subject))


def extract(inp: ExtractionInput) -> ExtractionResult:
    if inp.label == "OUT_OF_SCOPE":
        return ExtractionResult("SKIPPED", Header(), [], None, warnings=["out of scope (M03): nothing extracted"])
    cur = document_currency(inp)
    base, us = inp.email_date, inp.prefer_us_dates
    found: list[Line] = []
    table_totals = []
    for src in inp.sources:
        tl, totals = lines_from_tables(src, cur, base, us)
        found += tl
        table_totals += totals
        found += lines_from_text(src, cur, base, us)
    for m in find_refs(nfkc(inp.subject)):
        raw = clean_ref(m.group(0))
        subj = Source("subject", "body", "subject", inp.subject)
        found.append(Line(raw, normalise_ref(raw), subj, "mention", evidence={"ref": {"source": "subject", "text": raw}}))

    header = extract_header(inp, cur)
    if header.total is None and table_totals:
        t = table_totals[-1]
        header.total, header.payment_currency = (-t.value if t.negative else t.value), t.currency or header.payment_currency
    lines = _merge(found)
    _line_types(lines, inp, header)
    lines = _instalments(lines, inp, cur)
    for ln in lines:
        ln.payment_currency = ln.payment_currency or header.payment_currency or cur
        # ln.line_currency stays None when the document does not say the invoice's currency (M05 uses BSID)
    result = ExtractionResult("OK", header, lines, cur)
    _checks(result)
    return result


def _merge(found: list[Line]) -> list[Line]:
    groups: dict[str, list[Line]] = {}
    for ln in found:
        groups.setdefault(ln.ref_norm, []).append(ln)
    out = []
    for norm, group in groups.items():
        group.sort(key=lambda l: (l.amount is None, l.priority))
        best = group[0]
        best.in_ptp_sentence = any(l.in_ptp_sentence for l in group)
        for other in group[1:]:
            for attr in ("gross", "deduction", "deduction_reason", "invoice_date", "promise_date", "promise_text",
                         "line_currency", "payment_currency"):
                if getattr(best, attr) is None and getattr(other, attr) is not None:
                    setattr(best, attr, getattr(other, attr))
            best.credit_note = best.credit_note or other.credit_note
        amounts = {l.amount for l in group if l.amount is not None and l.method in ("table", "text_line", "prose")}
        best.evidence = {"best": best.evidence, "also_found": [{"method": l.method, "source": l.source.key,
                                                                  "amount": str(l.amount) if l.amount is not None else None}
                                                                 for l in group[1:]][:6]}
        if len(amounts) > 1:
            best.evidence["conflicting_amounts"] = sorted(str(a) for a in amounts)
        out.append(best)
    # keep the order of first appearance
    order = {ln.ref_norm: i for i, ln in reversed(list(enumerate(found)))}
    return sorted(out, key=lambda l: order[l.ref_norm])


def _line_types(lines: list[Line], inp: ExtractionInput, header: Header) -> None:
    for ln in lines:
        if not inp.contains_ptp:
            ln.line_type = "REMITTANCE"
        elif not inp.contains_remittance:
            ln.line_type = "PTP"
        else:
            ln.line_type = "PTP" if ln.in_ptp_sentence else "REMITTANCE"
        if ln.line_type == "PTP" and ln.promise_date is None and header.promise_date:
            ln.promise_date, ln.promise_text = header.promise_date, header.promise_text
        if ln.line_type == "REMITTANCE":
            ln.promise_date = ln.promise_text = None


def _instalments(lines: list[Line], inp: ExtractionInput, cur) -> list[Line]:
    ptp = [l for l in lines if l.line_type == "PTP"]
    if len(ptp) != 1:
        return lines
    plan = []
    for src in inp.sources:
        plan = instalments(src, cur, inp.email_date, inp.prefer_us_dates)
        if len(plan) >= 2:
            break
    if len(plan) < 2:
        return lines
    base = ptp[0]
    out = [l for l in lines if l is not base]
    for i, (d, amount, text) in enumerate(plan, start=1):
        out.append(Line(base.ref_raw, base.ref_norm, base.source, "instalment", amount=amount.value,
                        line_currency=base.line_currency or amount.currency, payment_currency=amount.currency,
                        promise_date=d, promise_text=text, instalment_no=i, line_type="PTP",
                        gross=base.amount if i == 1 else None,
                        evidence={"best": {"source": base.source.key, "text": text}, "ref": base.evidence}))
    return out


def _checks(r: ExtractionResult) -> None:
    if not r.lines:
        r.status = "NO_LINES"
        r.warnings.append("no invoice number found")
        return
    if any(l.amount is None for l in r.lines):
        r.status = "PARTIAL"
    rem = [l for l in r.lines if l.line_type == "REMITTANCE" and l.amount is not None]
    if rem and all(l.amount is not None for l in r.lines if l.line_type == "REMITTANCE"):
        r.lines_sum = sum((l.amount for l in rem), Decimal(0))
        line_curs = {l.payment_currency for l in rem} - {None}
        if r.header.payment_currency is None and len(line_curs) == 1:
            r.header.payment_currency = next(iter(line_curs))  # total written without a currency
        if r.header.total is not None:
            same_cur = {l.payment_currency for l in rem} <= {r.header.payment_currency, None}
            if same_cur:
                r.total_mismatch = r.header.total - r.lines_sum
                if abs(r.total_mismatch) > Decimal("0.01"):
                    r.warnings.append(f"total {r.header.total} differs from the sum of the lines {r.lines_sum}")
    for l in r.lines:
        if l.line_currency and l.payment_currency and l.line_currency != l.payment_currency and r.header.fx_rate is None:
            r.warnings.append(f"{l.ref_raw}: invoice in {l.line_currency}, paid in {l.payment_currency} (no FX rate stated)")
