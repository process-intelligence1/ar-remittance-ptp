"""Rows for one e-mail (no database writes): one per extracted invoice line, scored against BSID.

The caller adds what needs history: duplicates (duplicates.py) and payer / currency clusters.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.matching.customers import CustomerResult, identify, name_similarity
from app.matching.data import OpenItem, SapData
from app.matching.invoice_match import InvoiceMatch, find_matches, levels
from app.matching.scoring import Score, days_between, score
from app.matching.unreferenced import find_combinations

EXTRACTION_CONFIDENCE = {"table": 95, "instalment": 90, "text_line": 90, "prose": 80, "mention": 60, "amount": 70}


@dataclass
class LineIn:
    """One extracted line (from ar.extraction_line or an in-memory extraction result)."""
    ref_raw: str
    ref_norm: str | None
    line_type: str                  # REMITTANCE | PTP
    amount: Decimal | None = None
    gross: Decimal | None = None
    deduction: Decimal | None = None
    deduction_reason: str | None = None
    line_currency: str | None = None
    payment_currency: str | None = None
    credit_note: bool = False
    invoice_date: date | None = None
    promise_date: date | None = None
    promise_text: str | None = None
    instalment_no: int | None = None
    method: str = "table"
    evidence: dict | None = None
    extraction_line_id: int | None = None


@dataclass
class MatchInput:
    email_key: int | str
    label: str                      # M03: REMITTANCE | PTP | OUT_OF_SCOPE
    out_of_scope_category: str | None
    contains_remittance: bool
    sender_email: str | None
    sender_name: str | None
    received_at: datetime | None
    email_date: date | None
    business_date: date
    attachments: int
    lines: list[LineIn]
    payer_name: str | None = None
    customer_number: str | None = None
    payer_account: str | None = None
    payment_reference: str | None = None
    remittance_refs: list[str] = field(default_factory=list)
    payment_date: date | None = None
    total: Decimal | None = None
    payment_currency: str | None = None


@dataclass
class Candidate:
    item: OpenItem
    match: InvoiceMatch | None
    score: Score
    allowed: bool


@dataclass
class Row:
    line_no: int
    line_type: str | None
    final_classification: str
    line: LineIn | None
    kunnr: str | None
    bukrs: str | None
    customer_name: str | None
    customer: CustomerResult | None
    score: Score
    item: OpenItem | None = None
    match: InvoiceMatch | None = None
    match_type: str | None = None
    candidates: list[Candidate] = field(default_factory=list)
    amount: Decimal | None = None
    currency: str | None = None
    assigned_role: str | None = None
    sla_due_at: datetime | None = None
    out_of_scope_reason: str | None = None
    duplicate_of: object = None
    duplicate_reason: str | None = None
    payer_cluster_flag: bool | None = None
    currency_cluster_flag: bool | None = None


def _business_days(start: date, n: int) -> datetime:
    d = start
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return datetime(d.year, d.month, d.day, 17, 0)


def finish(row: Row, rules: dict, business_date: date) -> Row:
    """Role + SLA from the decision (called again after duplicates are applied)."""
    d = row.score.decision
    if d == "OUT_OF_SCOPE":
        row.assigned_role, row.sla_due_at = None, None
        return row
    if d in ("DUPLICATE", "EXCEPTION", "MANUAL_INVESTIGATION"):
        row.assigned_role = "AR_ANALYST"
    elif row.line_type == "PTP":
        row.assigned_role = "COLLECTIONS_ANALYST"
    else:
        row.assigned_role = "CASH_APPLICATION"
    sla = rules["sla"]
    if row.score.status == "EXCEPTION":
        row.sla_due_at = _business_days(business_date, sla["exception_business_days"])
    elif row.score.status in ("PENDING_REVIEW", "DUPLICATE"):
        row.sla_due_at = _business_days(business_date, sla["pending_review_business_days"])
    else:
        row.sla_due_at = None
    return row


def _compare_amount(line: LineIn, item: OpenItem, payment_currency: str | None) -> tuple[Decimal | None, str | None]:
    """The line amount to compare with BSID: the paid amount in the payment currency, or - when the
    payment was in another currency - the invoice (gross) amount in the invoice's own currency."""
    pay_cur = line.payment_currency or payment_currency
    if pay_cur and pay_cur != item.currency and line.gross is not None and line.line_currency == item.currency:
        return line.gross, line.line_currency
    return line.amount, (pay_cur or line.line_currency)


def match_email(inp: MatchInput, sap: SapData, rules: dict) -> list[Row]:
    im_cfg = rules["invoice_match"]
    cust_cfg = rules.get("customer_identification", {})
    rows: list[Row] = []

    if inp.label == "OUT_OF_SCOPE":
        s = Score(decision="OUT_OF_SCOPE", status="IGNORED", recommended_action="Ignore", category="LOW")
        rows.append(Row(1, None, "OUT_OF_SCOPE", None, None, None, None, None, s,
                        out_of_scope_reason=(inp.out_of_scope_category or "GENERAL").replace("_", " ").title()))
        return [finish(r, rules, inp.business_date) for r in rows]

    matches_by_line = [find_matches(l.ref_norm, sap, im_cfg) for l in inp.lines]
    exact_customers = [m.item.kunnr for ms in matches_by_line for m in ms if m.level == "EXACT"]
    cust = identify(sap, sender_email=inp.sender_email, customer_number=inp.customer_number,
                    iban=inp.payer_account, payer_name=inp.payer_name or inp.sender_name,
                    exact_invoice_customers=exact_customers, name_min=float(cust_cfg.get("name_similarity_min", 0.85)))
    sender_bukrs = set().union(*(sap.customers[k].bukrs for k in cust.sender_customers if k in sap.customers)) \
        if cust.sender_customers else set()
    when = inp.payment_date or inp.email_date

    def score_item(line: LineIn, item: OpenItem, m: InvoiceMatch | None, level: str, inv_score: float,
                   reasons: list[str]) -> Score:
        amount, cur = _compare_amount(line, item, inp.payment_currency)
        c = sap.customer(item.kunnr)
        return score(rules, level=level, invoice_score=inv_score, amount=amount, currency=cur,
                     bsid_amount=item.amount, bsid_currency=item.currency, sender_company=item.bukrs in sender_bukrs,
                     name_similarity=name_similarity(inp.payer_name or inp.sender_name, c.name if c else None),
                     date_days=days_between(when, item.bldat), review_reasons=reasons)

    for n, (line, ms) in enumerate(zip(inp.lines, matches_by_line), start=1):
        cands: list[Candidate] = []
        for m in ms:
            reasons = []
            if m.level == "NEAR":
                reasons.append(f"{levels(im_cfg)['NEAR'].get('reason', 'Possible OCR misread')} ({m.detail})")
            if m.item.blocked:
                reasons.append("Payment block on the open item (ZLSPR = R)")
            allowed = not cust.allowed or m.item.kunnr in cust.allowed
            if cust.payer_customers and m.item.kunnr not in cust.related:
                # third-party payment / wrong reference: the invoice's owner did not send this e-mail
                owner, sender = sap.customer(m.item.kunnr), sap.customer(sorted(cust.payer_customers)[0])
                reasons.append(f"Invoice belongs to customer {m.item.kunnr.lstrip('0')} ({owner.name if owner else '?'}), "
                               f"but the e-mail comes from customer {sorted(cust.payer_customers)[0].lstrip('0')} "
                               f"({sender.name if sender else '?'})")
            elif not allowed:
                reasons.append(f"Invoice belongs to customer {m.item.kunnr.lstrip('0')}, not to the identified payer")
            if len([x for x in ms if x.level == m.level]) > 1:
                reasons.append("Several open items carry this number")
            if line.line_type == "PTP" and line.promise_date is None:
                reasons.append("Promise date missing")
            cands.append(Candidate(m.item, m, score_item(line, m.item, m, m.level, m.score, reasons), allowed))
        cands.sort(key=lambda c: (not c.allowed, c.match.level != "EXACT", c.match.field != im_cfg.get("primary_field", "XBLNR"),
                                  -c.score.confidence))
        if cands:
            best = cands[0]
            item = best.item
            c = sap.customer(item.kunnr)
            row = Row(n, line.line_type, line.line_type, line, item.kunnr, item.bukrs, c.name if c else None, cust,
                      best.score, item, best.match, f"INVOICE_{best.match.level}", cands,
                      line.amount, line.payment_currency or inp.payment_currency or line.line_currency)
        else:
            reasons = ["Promise date missing"] if line.line_type == "PTP" and line.promise_date is None else []
            s = score(rules, level="NONE", invoice_score=0.0, amount=line.amount, currency=None, bsid_amount=None,
                      bsid_currency=None, sender_company=False, name_similarity=0.0, date_days=None, review_reasons=reasons)
            k = cust.kunnr
            c = sap.customer(k)
            row = Row(n, line.line_type, "EXCEPTION", line, k, _single_bukrs(c), c.name if c else None, cust, s,
                      match_type="INVOICE_NONE", amount=line.amount,
                      currency=line.payment_currency or inp.payment_currency or line.line_currency)
        rows.append(row)

    if not inp.lines:
        rows += _unreferenced(inp, sap, rules, cust, score_item)
    return [finish(r, rules, inp.business_date) for r in rows]


def _single_bukrs(c) -> str | None:
    return next(iter(c.bukrs)) if c and len(c.bukrs) == 1 else None


def _unreferenced(inp: MatchInput, sap: SapData, rules: dict, cust: CustomerResult, score_item) -> list[Row]:
    """No invoice numbers: open invoices of the payer that add up to the paid amount (always reviewed)."""
    cfg = rules["unreferenced_payment"]
    line_type = "REMITTANCE" if inp.contains_remittance else "PTP"
    pool = [i for k in (cust.allowed or set()) for i in sap.by_kunnr.get(k, [])
            if i.currency == inp.payment_currency and not i.blocked]
    combos = find_combinations(inp.total, pool, tolerance_pct=cfg["amount_tolerance_pct"],
                               max_invoices=cfg["max_invoices"]) if cfg.get("enabled", True) and line_type == "REMITTANCE" else []
    if combos:
        best = combos[0]
        rows = []
        for n, item in enumerate(best.items, start=1):
            line = LineIn(ref_raw="", ref_norm=None, line_type=line_type, amount=item.amount,
                          payment_currency=inp.payment_currency, method="amount",
                          evidence={"note": "no invoice number in the e-mail - found by amount",
                                    "paid": str(inp.total), "combination_total": str(best.total),
                                    "difference": str(best.difference), "alternatives": len(combos) - 1})
            reasons = [f"No invoice number - matched by amount ({len(best.items)} invoice(s), "
                       f"difference {best.difference} {inp.payment_currency})"]
            s = score_item(line, item, None, "AMOUNT", 0.0, reasons)
            if s.decision == "AUTO_PROCESS":
                s.decision, s.status = "MANUAL_REVIEW", "PENDING_REVIEW"
            s.recommended_action = "Add / Update Invoice Details"
            c = sap.customer(item.kunnr)
            alt = [Candidate(i, None, s, True) for combo in combos[1:] for i in combo.items][:10]
            rows.append(Row(n, line_type, line_type, line, item.kunnr, item.bukrs, c.name if c else None, cust, s, item,
                            None, "AMOUNT_COMBINATION", [Candidate(item, None, s, True)] + alt, item.amount,
                            inp.payment_currency))
        return rows
    s = score(rules, level="NONE", invoice_score=0.0, amount=inp.total, currency=inp.payment_currency, bsid_amount=None,
              bsid_currency=None, sender_company=False, name_similarity=0.0, date_days=None)
    s.exception_reason = "No invoice reference found" + ("" if inp.total else " and no amount stated")
    c = sap.customer(cust.kunnr)
    line = LineIn(ref_raw="", ref_norm=None, line_type=line_type, amount=inp.total, payment_currency=inp.payment_currency,
                  method="amount", evidence={"note": "no invoice number and no combination of open invoices found"})
    return [Row(1, line_type, "EXCEPTION", line, cust.kunnr, _single_bukrs(c), c.name if c else None, cust, s,
                match_type="NO_REFERENCE", amount=inp.total, currency=inp.payment_currency)]


def mark_duplicate(row: Row, original, reason: str, rules: dict, business_date: date) -> Row:
    """The row repeats an earlier one: DUPLICATE, pointing to the original (scores are kept)."""
    row.final_classification = "DUPLICATE"
    row.score.decision, row.score.status = "DUPLICATE", "DUPLICATE"
    row.score.recommended_action = "Close as Duplicate"
    row.duplicate_of, row.duplicate_reason = original, reason
    return finish(row, rules, business_date)


def set_clusters(row: Row, history: list[tuple[str, str, str]], min_history: int, sender_domain: str | None) -> None:
    """Payer / currency cluster from the customer's past rows (kunnr, sender domain, currency).
    Left blank (None) when there is not enough history."""
    past = [h for h in history if h[0] == row.kunnr and h[1] == sender_domain]
    if not row.kunnr or len(past) < min_history:
        row.payer_cluster_flag = row.currency_cluster_flag = None
        return
    row.payer_cluster_flag = True
    row.currency_cluster_flag = any(h[2] == row.currency for h in past)
