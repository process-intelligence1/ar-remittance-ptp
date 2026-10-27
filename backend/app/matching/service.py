"""Match a stored e-mail (after M04 extraction): ar.work_item rows (one per invoice), their
ar.match_candidate rows, and ar.ptp_commitment rows for promises.

Re-running replaces only rows nobody has worked on yet (not resolved, not rejected); if an analyst has
already acted on a row of this e-mail, the e-mail is left alone. E-mail status -> PROCESSED, audit
entry WORK_ITEMS_CREATED.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.classification.service import current_classification
from app.extraction.service import current_extraction
from app.gmail.poller import current_business_date
from app.matching.adapters import from_db
from app.matching.data import SapData, load_sap
from app.matching.duplicates import RowKey, find_original
from app.matching.matcher import Row, mark_duplicate, match_email, set_clusters
from app.models.ar import (AuditLog, EmailAttachment, EmailMessage, ExtractionLine, MatchCandidate, PtpCommitment,
                           RuleConfig, WorkItem)
from app.rules_defaults import DEFAULT_RULES

MATCHABLE = ("EXTRACTED", "PROCESSED")
UNTOUCHED = ("AUTO_PROCESSED", "PENDING_REVIEW", "EXCEPTION", "DUPLICATE", "IGNORED")


class NotExtractedYet(Exception):
    """M04 has not extracted this e-mail yet."""


class AlreadyWorkedOn(Exception):
    """An analyst has acted on a row of this e-mail - it is not re-matched automatically."""


def all_rules(db: Session) -> dict:
    rules = {k: v[0] for k, v in DEFAULT_RULES.items()}
    for row in db.scalars(select(RuleConfig)):
        if isinstance(row.value, dict) and row.key in rules:
            rules[row.key] = {**rules[row.key], **row.value}
    return rules


def _json(v):
    if isinstance(v, dict):
        return {k: _json(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [_json(x) for x in v]
    if isinstance(v, (Decimal, date)):
        return str(v)
    return v


def _history(db: Session, email: EmailMessage) -> tuple[list[RowKey], list[tuple[str, str, str]]]:
    """Rows of OTHER, earlier e-mails (duplicates are never originals) + their attachment hashes."""
    hashes: dict[int, set[str]] = {}
    for eid, sha in db.execute(select(EmailAttachment.email_id, EmailAttachment.sha256)
                               .where(EmailAttachment.sha256.is_not(None), EmailAttachment.is_inline.is_(False))):
        hashes.setdefault(eid, set()).add(sha)
    q = (select(WorkItem, EmailMessage).join(EmailMessage, EmailMessage.id == WorkItem.email_id)
         .where(WorkItem.email_id != email.id, WorkItem.final_classification != "DUPLICATE")
         .order_by(WorkItem.id))
    keys, clusters = [], []
    for wi, em in db.execute(q):
        if email.received_at and em.received_at and em.received_at > email.received_at:
            continue  # only earlier e-mails can be the original
        keys.append(RowKey(wi.id, em.id, wi.invoice_ref_norm, wi.kunnr, wi.amount, wi.currency, em.sender_domain,
                           em.received_at, frozenset(hashes.get(em.id, set())), wi.line_type))
        if wi.kunnr:
            clusters.append((wi.kunnr, em.sender_domain, wi.currency))
    return keys, clusters


NEXT_ENTRY = text("SELECT nextval('ar.entry_id_seq')")


def _entry_id(db: Session) -> str:
    return f"ENT-{db.execute(NEXT_ENTRY).scalar_one():06d}"


def match_stored_email(db: Session, email: EmailMessage, sap: SapData | None = None) -> list[WorkItem]:
    if email.status not in MATCHABLE:
        raise NotExtractedYet(f"{email.email_ref} is {email.status} - read, classify and extract it first")
    x = current_extraction(db, email.id)
    cls = current_classification(db, email.id)
    if x is None or cls is None:
        raise NotExtractedYet(f"{email.email_ref} has no extraction yet - run M04 first")
    existing = db.scalars(select(WorkItem).where(WorkItem.email_id == email.id)).all()
    if any(w.status not in UNTOUCHED or w.resolved_at for w in existing):
        raise AlreadyWorkedOn(f"{email.email_ref}: an analyst has already acted on its rows")
    # duplicates in OTHER e-mails that point to rows about to be replaced: unhook now, re-point afterwards
    old_by_id = {w.id: (w.invoice_ref_norm, w.line_no) for w in existing}
    pointing = db.scalars(select(WorkItem).where(WorkItem.duplicate_of_id.in_(list(old_by_id)),
                                                 WorkItem.email_id != email.id)).all() if existing else []
    repoint = [(w, old_by_id[w.duplicate_of_id]) for w in pointing]
    for w, _ in repoint:
        w.duplicate_of_id = None
    if existing:
        db.flush()
        db.execute(delete(WorkItem).where(WorkItem.email_id == email.id))  # candidates / promises cascade

    rules = all_rules(db)
    sap = sap or load_sap(db)
    bd = current_business_date(db)
    lines = db.scalars(select(ExtractionLine).where(ExtractionLine.extraction_id == x.id)
                       .order_by(ExtractionLine.line_no)).all()
    atts = db.scalars(select(EmailAttachment).where(EmailAttachment.email_id == email.id,
                                                    EmailAttachment.is_inline.is_(False))).all()
    inp = from_db(email, x, lines, label=cls.label, out_of_scope_category=cls.out_of_scope_category,
                  contains_remittance=cls.contains_remittance, attachments=len([a for a in atts if a.depth == 0]),
                  business_date=bd)
    rows = match_email(inp, sap, rules)

    history, clusters = _history(db, email)
    my_hashes = frozenset(a.sha256 for a in atts if a.sha256)
    by_id = {}
    for row in rows:
        if row.final_classification == "OUT_OF_SCOPE":
            continue
        key = RowKey("new", email.id, row.line.ref_norm if row.line else None, row.kunnr, row.amount, row.currency,
                     email.sender_domain, email.received_at, my_hashes, row.line_type)
        original, reason = find_original(key, history, rules["duplicate_detection"])
        if original:
            mark_duplicate(row, original.row_id, reason, rules, bd)
        set_clusters(row, clusters, int(rules["customer_identification"].get("cluster_min_history", 3)),
                     email.sender_domain)

    saved = []
    for row in rows:
        wi = _work_item(db, email, x, row, inp, bd)
        db.add(wi)
        db.flush()
        by_id[row.line_no] = wi
        for rank, c in enumerate(row.candidates[:10], start=1):
            db.add(MatchCandidate(work_item_id=wi.id, bsid_id=c.item.id, rank=rank,
                                  scores=_json(c.score.as_dict() | {"field": c.match.field if c.match else None,
                                                                    "level": c.match.level if c.match else None,
                                                                    "allowed_customer": c.allowed}),
                                  confidence_score=c.score.confidence, chosen=(rank == 1 and row.item is not None)))
        if row.line_type == "PTP" and row.line and row.line.promise_date and row.final_classification == "PTP":
            db.add(PtpCommitment(work_item_id=wi.id, kunnr=row.kunnr, bukrs=row.bukrs,
                                 bsid_id=row.item.id if row.item else None, instalment_no=row.line.instalment_no or 1,
                                 promise_date=row.line.promise_date,
                                 amount=row.amount if row.amount is not None else (row.item.amount if row.item else None),
                                 currency=row.currency or (row.item.currency if row.item else None), status="OPEN"))
        saved.append(wi)
    for w, (inv, line_no) in repoint:  # the same invoice (or line) in the new rows is the original again
        new = next((s for s in saved if inv and s.invoice_ref_norm == inv), None) or \
            next((s for s in saved if s.line_no == line_no), None)
        w.duplicate_of_id = new.id if new else None
    email.status = "PROCESSED"
    db.add(AuditLog(business_date=bd, actor="system", entity_type="email", entity_id=email.email_ref,
                    action="WORK_ITEMS_CREATED",
                    details={"rows": [{"entry_id": w.entry_id, "invoice": w.invoice_ref_raw, "decision": w.decision,
                                       "confidence": str(w.confidence_score) if w.confidence_score is not None else None,
                                       "source": w.confidence_source} for w in saved],
                             "customer": rows[0].kunnr if rows else None,
                             "customer_method": rows[0].customer.method if rows and rows[0].customer else None,
                             "replaced": len(existing)}))
    db.commit()
    return saved


def _work_item(db: Session, email: EmailMessage, x, row: Row, inp, bd: date) -> WorkItem:
    s, line, item = row.score, row.line, row.item
    return WorkItem(
        entry_id=_entry_id(db), email_id=email.id, line_no=row.line_no, line_type=row.line_type,
        final_classification=row.final_classification, customer_name=row.customer_name, kunnr=row.kunnr, bukrs=row.bukrs,
        invoice_ref_raw=(line.ref_raw or None) if line else None, invoice_ref_norm=line.ref_norm if line else None,
        invoice_date=line.invoice_date if line else None,
        remittance_ref=(inp.payment_reference or (inp.remittance_refs[0] if inp.remittance_refs else None)),
        amount=row.amount, currency=row.currency, payment_date=inp.payment_date,
        promise_date=line.promise_date if line else None, deduction_amount=line.deduction if line else None,
        deduction_reason=line.deduction_reason if line else None, credit_note_flag=bool(line and line.credit_note),
        body_only_flag=inp.attachments == 0, multi_attachment_flag=inp.attachments > 1,
        extraction_confidence=Decimal({"table": 95, "instalment": 90, "text_line": 90, "prose": 80, "mention": 60,
                                       "amount": 70}.get(line.method, 60)) if line else None,
        extraction_evidence=_json(line.evidence) if line and line.evidence else None,
        extraction_line_id=line.extraction_line_id if line else None,
        bsid_id=item.id if item else None, bsid_match_flag=item is not None,
        bsid_open_item_status="OPEN" if item else None, match_type=row.match_type,
        match_field=row.match.field if row.match else None, match_level=row.match.level if row.match else (
            "NONE" if row.match_type == "INVOICE_NONE" else None),
        invoice_match_score=Decimal(str(s.invoice_match)), amount_difference_pct=s.amount_difference_pct,
        amount_alignment_score=Decimal(str(s.amount_alignment)), sender_company_score=Decimal(str(s.sender_company)),
        customer_name_similarity=Decimal(str(round(s.customer_name, 4))), date_difference_days=s.date_difference_days,
        date_proxy_score=Decimal(str(s.date_proxy)), payer_cluster_flag=row.payer_cluster_flag,
        currency_cluster_flag=row.currency_cluster_flag, raw_score=s.raw, confidence_score=s.confidence,
        confidence_category=s.category, fast_path_override=s.fast_path, confidence_source=s.confidence_source,
        formula_confidence=s.formula_confidence, review_reasons=s.review_reasons or None,
        decision=s.decision, status=s.status, exception_reason=s.exception_reason,
        out_of_scope_reason=row.out_of_scope_reason, duplicate_of_id=row.duplicate_of if isinstance(row.duplicate_of, int) else None,
        recommended_action=s.recommended_action, assigned_role=row.assigned_role, sla_due_at=row.sla_due_at,
        customer_match_method=row.customer.method if row.customer else None,
        customer_match_score=Decimal(str(row.customer.score)) if row.customer and row.customer.method else None,
        customer_evidence=_json(row.customer.evidence) | ({"duplicate_reason": row.duplicate_reason}
                                                          if row.duplicate_reason else {}) if row.customer else None)
