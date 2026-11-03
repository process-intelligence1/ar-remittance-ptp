"""Re-match and re-score ONE existing work item after an analyst changed its details (M09).

Uses the same rules and scoring as the pipeline (match_email / score): the edited values become the row's single
extracted line, the customer number is the one the analyst gave, and - when the analyst picked a BSID item - that item
is scored as the match. Nothing is written to sap.*; the row, its candidates and a before / after summary are updated.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.extraction.refs import normalise_ref
from app.matching.customers import identify, name_similarity
from app.matching.data import SapData
from app.matching.invoice_match import compare, levels
from app.matching.matcher import Candidate, LineIn, MatchInput, Row, _compare_amount, finish, mark_duplicate, match_email
from app.matching.scoring import days_between, score
from app.models.ar import EmailMessage, Extraction, MatchCandidate, WorkItem
from app.permissions import OPEN_WORKFLOW

class DetailsError(ValueError):
    """The analyst's input is not usable (shown to the user as a 422)."""


@dataclass
class Edit:
    values: dict            # only the fields the analyst changed (keys of EDITABLE)
    bsid_id: int | None = None


def _parse(edit: Edit, sap: SapData) -> dict:
    """Validated, typed values for the work item columns."""
    out: dict = {}
    v = edit.values
    if "invoice_ref" in v:
        ref = (v["invoice_ref"] or "").strip()
        out["invoice_ref_raw"], out["invoice_ref_norm"] = (ref or None), normalise_ref(ref) if ref else None
    if "amount" in v:
        raw = str(v["amount"] if v["amount"] is not None else "").strip().replace(",", "")
        try:
            out["amount"] = Decimal(raw) if raw else None
        except Exception as exc:
            raise DetailsError("Amount is not a number.") from exc
    if "currency" in v:
        cur = (v["currency"] or "").strip().upper()
        if cur and (len(cur) != 3 or not cur.isalpha()):
            raise DetailsError("Currency must be a 3-letter code such as USD.")
        out["currency"] = cur or None
    if "payment_date" in v:
        try:
            out["payment_date"] = date.fromisoformat(v["payment_date"]) if v["payment_date"] else None
        except ValueError as exc:
            raise DetailsError("Payment date must be YYYY-MM-DD.") from exc
    if "payment_reference" in v:
        out["remittance_ref"] = (v["payment_reference"] or "").strip()[:60] or None
    if "kunnr" in v:
        written = (v["kunnr"] or "").strip()
        if written:
            k = sap.find_kunnr(written)
            if k is None:
                raise DetailsError(f"Customer {written} does not exist.")
            out["kunnr"] = k
        else:
            out["kunnr"] = None
    if "bukrs" in v:
        b = (v["bukrs"] or "").strip()
        out["bukrs"] = b or None
    return out


def _score_against(inp: MatchInput, sap: SapData, rules: dict, line: LineIn, item, cust) -> Candidate:
    """Score `line` against a BSID item the analyst picked (same formula as the pipeline)."""
    im_cfg = rules["invoice_match"]
    level, detail = "NONE", None
    for ref in (item.xblnr, item.belnr, item.vbeln):
        lv, d = compare(line.ref_norm, normalise_ref(ref), im_cfg)
        if lv == "EXACT" or (lv == "NEAR" and level == "NONE"):
            level, detail = lv, d
            if lv == "EXACT":
                break
    reasons = []
    if level == "NONE":
        level = "MANUAL"  # the analyst linked it by hand: the number does not match, so the invoice part scores 0
        reasons.append("BSID item selected by the analyst (invoice number does not match)")
    elif level == "NEAR":
        reasons.append(f"{levels(im_cfg)['NEAR'].get('reason', 'Possible OCR misread')} ({detail})")
    if item.blocked:
        reasons.append("Payment block on the open item (ZLSPR = R)")
    sender_bukrs = set().union(*(sap.customers[k].bukrs for k in cust.sender_customers if k in sap.customers)) \
        if cust.sender_customers else set()
    amount, cur = _compare_amount(line, item, inp.payment_currency)
    c = sap.customer(item.kunnr)
    inv_score = float(levels(im_cfg).get(level, {}).get("score", 0.0))
    s = score(rules, level=level, invoice_score=inv_score, amount=amount, currency=cur, bsid_amount=item.amount,
              bsid_currency=item.currency, sender_company=item.bukrs in sender_bukrs,
              name_similarity=name_similarity(inp.payer_name or inp.sender_name, c.name if c else None),
              date_days=days_between(inp.payment_date or inp.email_date, item.bldat), review_reasons=reasons)
    return Candidate(item, None, s, True)


def rescore(db: Session, w: WorkItem, e: EmailMessage, edit: Edit, sap: SapData, rules: dict, business_date: date,
            *, drop_duplicate: bool = False) -> None:
    """Apply `edit` to the work item, then match and score it again."""
    typed = _parse(edit, sap)
    for k, v in typed.items():
        setattr(w, k, v)
    if edit.bsid_id is not None and edit.bsid_id not in sap.items:
        raise DetailsError("The selected BSID item is not an open item.")

    x = db.scalar(select(Extraction).where(Extraction.email_id == e.id, Extraction.is_current.is_(True)))
    line = LineIn(ref_raw=w.invoice_ref_raw or "", ref_norm=w.invoice_ref_norm, line_type=w.line_type or "REMITTANCE",
                  amount=w.amount, payment_currency=w.currency, credit_note=bool(w.credit_note_flag),
                  invoice_date=w.invoice_date, promise_date=w.promise_date, method="table",
                  evidence=w.extraction_evidence)
    inp = MatchInput(
        email_key=e.id, label=w.line_type or "REMITTANCE", out_of_scope_category=None,
        contains_remittance=(w.line_type != "PTP"), sender_email=e.sender_email, sender_name=e.sender_name,
        received_at=e.received_at, email_date=e.received_at.date() if e.received_at else business_date,
        business_date=business_date, attachments=0, lines=[line],
        payer_name=x.payer_name if x else w.customer_name, customer_number=w.kunnr,
        payer_account=x.payer_account if x else None, payment_reference=w.remittance_ref,
        payment_date=w.payment_date, total=w.amount, payment_currency=w.currency)

    row: Row = match_email(inp, sap, rules)[0]
    if edit.bsid_id is not None:  # the analyst's choice wins over the best automatic candidate
        item = sap.items[edit.bsid_id]
        cust = row.customer or identify(sap, sender_email=e.sender_email, customer_number=w.kunnr, iban=None,
                                        payer_name=inp.payer_name, exact_invoice_customers=[], name_min=0.85)
        chosen = _score_against(inp, sap, rules, line, item, cust)
        row.candidates = [chosen] + [c for c in row.candidates if c.item.id != item.id]
        c = sap.customer(item.kunnr)
        row.item, row.match, row.score = item, None, chosen.score
        row.match_type, row.final_classification = "ANALYST_SELECTED", line.line_type
        row.kunnr, row.bukrs, row.customer_name = item.kunnr, item.bukrs, c.name if c else None
        row.amount, row.currency = w.amount, w.currency or item.currency
        finish(row, rules, business_date)
    if w.duplicate_of_id and not drop_duplicate:  # editing does not clear the duplicate flag; only "Mark as Non-Duplicate" does
        mark_duplicate(row, w.duplicate_of_id, (w.customer_evidence or {}).get("duplicate_reason", "duplicate"), rules,
                       business_date)

    _apply(db, w, row, keep_status=w.status in OPEN_WORKFLOW, drop_duplicate=drop_duplicate)


def _apply(db: Session, w: WorkItem, row: Row, *, keep_status: bool, drop_duplicate: bool) -> None:
    s, item = row.score, row.item
    w.final_classification = row.final_classification
    w.customer_name, w.kunnr = row.customer_name or w.customer_name, row.kunnr or w.kunnr
    w.bukrs = row.bukrs or w.bukrs
    w.bsid_id, w.bsid_match_flag = (item.id if item else None), item is not None
    w.region = item.region if item else w.region
    w.bsid_open_item_status = "OPEN" if item else None
    w.match_type = row.match_type
    w.match_field = row.match.field if row.match else None
    w.match_level = row.match.level if row.match else ("NONE" if row.match_type == "INVOICE_NONE" else
                                                       "MANUAL" if row.match_type == "ANALYST_SELECTED" else None)
    w.invoice_match_score = Decimal(str(s.invoice_match))
    w.amount_difference_pct, w.amount_alignment_score = s.amount_difference_pct, Decimal(str(s.amount_alignment))
    w.sender_company_score, w.customer_name_similarity = Decimal(str(s.sender_company)), Decimal(str(round(s.customer_name, 4)))
    w.date_difference_days, w.date_proxy_score = s.date_difference_days, Decimal(str(s.date_proxy))
    w.raw_score, w.confidence_score, w.confidence_category = s.raw, s.confidence, s.category
    w.fast_path_override, w.confidence_source, w.formula_confidence = s.fast_path, s.confidence_source, s.formula_confidence
    w.review_reasons = s.review_reasons or None
    w.decision, w.exception_reason, w.recommended_action = s.decision, s.exception_reason, s.recommended_action
    if not keep_status:
        w.status = s.status
        w.assigned_role = row.assigned_role
    w.sla_due_at = row.sla_due_at
    if drop_duplicate:
        w.duplicate_of_id = None
        ev = dict(w.customer_evidence or {})
        ev.pop("duplicate_reason", None)
        w.customer_evidence = ev or None
    # the candidate list shown for the row: replace it with the new one
    db.execute(delete(MatchCandidate).where(MatchCandidate.work_item_id == w.id))
    for rank, c in enumerate(row.candidates[:10], start=1):
        db.add(MatchCandidate(work_item_id=w.id, bsid_id=c.item.id, rank=rank, confidence_score=c.score.confidence,
                              chosen=(rank == 1 and item is not None),
                              scores=c.score.as_dict() | {"field": c.match.field if c.match else None,
                                                          "level": c.match.level if c.match else None,
                                                          "allowed_customer": c.allowed}))
