"""Workbench API (M07): work items (one row per invoice), their detail, attachment files and the change feed.

Everything here needs a signed-in demo user (Authorization: Bearer <token>), except the attachment file download,
which uses a short-lived signed link (?token=) so a browser PDF / image viewer can load it without a header.
Every row says which actions the current user may take (app/permissions.py).
"""
import mimetypes
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response
from sqlalchemy import and_, asc, desc, func, inspect, or_, select, text
from sqlalchemy.orm import Session

from app.api.auth import CurrentUser, current_user, make_file_token, read_token
from app.db import get_db
from app.fx import get_rates
from app.models.ar import (AuditLog, EmailAttachment, EmailClassification, EmailMessage, Extraction, ExtractionLine,
                           MatchCandidate, PtpCommitment, WorkItem)
from app.permissions import allowed_actions
from app.storage import get_storage

router = APIRouter(prefix="/api", tags=["Workbench"])

MAX_PAGE = 200
CHANGES_OVERLAP_S = 60
INLINE_TYPES = ("application/pdf", "image/png", "image/jpeg", "image/tiff", "image/gif", "text/plain", "text/csv")


# --------------------------------------------------------------------------- filters (shared with the KPIs)
@dataclass
class Filters:
    from_date: date | None = None
    to_date: date | None = None
    classification: str | None = None
    bsid_match: bool | None = None
    status: str | None = None
    decision: str | None = None
    min_confidence: float | None = None
    max_confidence: float | None = None
    customer: str | None = None
    company_code: str | None = None
    region: str | None = None
    q: str | None = None


def filters(from_date: date | None = None, to_date: date | None = None, classification: str | None = None,
            bsid_match: bool | None = None, status: str | None = None, decision: str | None = None,
            min_confidence: float | None = Query(None, ge=0, le=100), max_confidence: float | None = Query(None, ge=0, le=100),
            customer: str | None = Query(None, description="customer number or part of the name"),
            company_code: str | None = None, region: str | None = None,
            q: str | None = Query(None, description="entry id, e-mail ref, invoice number, customer, sender")) -> Filters:
    return Filters(from_date, to_date, classification, bsid_match, status, decision, min_confidence, max_confidence,
                   customer, company_code, region, q)


def received_date():
    return func.date(func.coalesce(EmailMessage.received_at, EmailMessage.created_at))


def apply_filters(query, f: Filters):
    c = []
    if f.from_date:
        c.append(received_date() >= f.from_date)
    if f.to_date:
        c.append(received_date() <= f.to_date)
    if f.classification:
        c.append(WorkItem.final_classification == f.classification.upper())
    if f.bsid_match is not None:
        c.append(WorkItem.bsid_match_flag.is_(f.bsid_match))
    if f.status:
        c.append(WorkItem.status == f.status.upper())
    if f.decision:
        c.append(WorkItem.decision == f.decision.upper())
    if f.min_confidence is not None:
        c.append(WorkItem.confidence_score >= f.min_confidence)
    if f.max_confidence is not None:
        c.append(WorkItem.confidence_score <= f.max_confidence)
    if f.customer:
        k = f.customer.strip()
        c.append(or_(WorkItem.kunnr == k.zfill(10), WorkItem.kunnr == k, WorkItem.customer_name.ilike(f"%{k}%")))
    if f.company_code:
        c.append(WorkItem.bukrs == f.company_code)
    if f.region:
        c.append(WorkItem.region == f.region)
    if f.q:
        like = f"%{f.q.strip()}%"
        c.append(or_(WorkItem.entry_id.ilike(like), EmailMessage.email_ref.ilike(like), WorkItem.invoice_ref_raw.ilike(like),
                     WorkItem.invoice_ref_norm.ilike(like), WorkItem.customer_name.ilike(like),
                     EmailMessage.sender_email.ilike(like), EmailMessage.subject.ilike(like)))
    return query.where(and_(*c)) if c else query


SORTS = {
    "received_at": EmailMessage.received_at, "entry_id": WorkItem.entry_id, "confidence": WorkItem.confidence_score,
    "amount": WorkItem.amount, "customer": WorkItem.customer_name, "status": WorkItem.status,
    "decision": WorkItem.decision, "sla_due_at": WorkItem.sla_due_at, "company_code": WorkItem.bukrs,
    "classification": WorkItem.final_classification, "updated_at": WorkItem.updated_at,
}


# --------------------------------------------------------------------------- serialising
def columns(obj, exclude: tuple[str, ...] = ()) -> dict:
    return {a.key: getattr(obj, a.key) for a in inspect(obj).mapper.column_attrs if a.key not in exclude}


def row_date(w: WorkItem, e: EmailMessage) -> date | None:
    """The date a row's USD value is converted at: payment date, else the day the e-mail arrived."""
    if w.payment_date:
        return w.payment_date
    stamp = e.received_at or e.created_at
    return stamp.date() if stamp else None


def usd_fields(rates, w: WorkItem, e: EmailMessage) -> dict:
    usd, status = rates.to_usd(w.amount, w.currency, row_date(w, e))
    return {"amount_usd": usd, "usd_status": status}  # NO_RATE / NO_AMOUNT rows are flagged, never counted as 0


def summary(w: WorkItem, e: EmailMessage, user: CurrentUser, rates, original_entry: str | None = None) -> dict:
    return {
        "id": w.id, "entry_id": w.entry_id, "email_ref": e.email_ref, "received_at": e.received_at,
        "sender_email": e.sender_email, "subject": e.subject, "sample_code": e.sample_code,
        "customer_name": w.customer_name, "kunnr": w.kunnr, "company_code": w.bukrs, "region": w.region,
        "classification": w.final_classification, "line_type": w.line_type, "invoice_ref": w.invoice_ref_raw,
        "match_field": w.match_field, "match_level": w.match_level, "bsid_match": w.bsid_match_flag,
        "amount": w.amount, "currency": w.currency, **usd_fields(rates, w, e),
        "confidence": w.confidence_score, "confidence_source": w.confidence_source, "decision": w.decision,
        "status": w.status, "exception_reason": w.exception_reason, "review_reasons": w.review_reasons,
        "recommended_action": w.recommended_action, "assigned_role": w.assigned_role, "sla_due_at": w.sla_due_at,
        "duplicate_of": original_entry, "body_only": w.body_only_flag, "updated_at": w.updated_at,
        "allowed_actions": allowed_actions(user.role, w.decision, w.status, w.assigned_role, bool(w.resolved_at)),
    }


# --------------------------------------------------------------------------- list
@router.get("/work-items", summary="Action Queue: work items (one row per invoice), filtered, sorted, paged")
def list_work_items(f: Filters = Depends(filters), sort: str = Query("received_at"), order: str = Query("desc"),
                    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=MAX_PAGE),
                    user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    if sort not in SORTS:
        raise HTTPException(422, f"sort must be one of {sorted(SORTS)}")
    base = apply_filters(select(WorkItem, EmailMessage).join(EmailMessage, EmailMessage.id == WorkItem.email_id), f)
    total = db.scalar(select(func.count()).select_from(base.with_only_columns(WorkItem.id).order_by(None).subquery()))
    direction = asc if order.lower() == "asc" else desc
    rows = db.execute(base.order_by(direction(SORTS[sort]).nulls_last(), WorkItem.id.desc())
                      .limit(page_size).offset((page - 1) * page_size)).all()
    originals = {}
    ids = [w.duplicate_of_id for w, _ in rows if w.duplicate_of_id]
    if ids:
        originals = dict(db.execute(select(WorkItem.id, WorkItem.entry_id).where(WorkItem.id.in_(ids))).all())
    rates = get_rates(db)
    return {"total": total, "page": page, "page_size": page_size,
            "items": jsonable_encoder([summary(w, e, user, rates, originals.get(w.duplicate_of_id)) for w, e in rows])}


# --------------------------------------------------------------------------- detail
def _find(db: Session, item_id: str) -> WorkItem:
    w = db.get(WorkItem, int(item_id)) if item_id.isdigit() else \
        db.scalar(select(WorkItem).where(WorkItem.entry_id == item_id.upper()))
    if w is None:
        raise HTTPException(404, f"Work item {item_id} not found")
    return w


@router.get("/work-items/{item_id}", summary="Record Detail: e-mail, attachments (signed links), evidence, candidates, audit")
def work_item_detail(item_id: str, user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    w = _find(db, item_id)
    e = db.get(EmailMessage, w.email_id)
    rates = get_rates(db)
    original = db.get(WorkItem, w.duplicate_of_id) if w.duplicate_of_id else None

    atts = db.scalars(select(EmailAttachment).where(EmailAttachment.email_id == e.id).order_by(EmailAttachment.id)).all()
    attachments = []
    for a in atts:
        meta = columns(a, exclude=("layout", "text_content", "storage_uri"))
        meta["chars"] = len(a.text_content or "")
        meta["url"] = f"/api/attachments/{a.id}/file?token={make_file_token(a.id, user.email)}"  # about 5 minutes
        meta["viewable_inline"] = (a.mime_type or "") in INLINE_TYPES
        attachments.append(meta)

    cls = db.scalar(select(EmailClassification).where(EmailClassification.email_id == e.id,
                                                      EmailClassification.is_current.is_(True)))
    ext = db.scalar(select(Extraction).where(Extraction.email_id == e.id, Extraction.is_current.is_(True)))
    line = db.get(ExtractionLine, w.extraction_line_id) if w.extraction_line_id else None
    cands = db.scalars(select(MatchCandidate).where(MatchCandidate.work_item_id == w.id)
                       .order_by(MatchCandidate.rank)).all()
    items = {}
    if cands:
        items = {r.id: dict(r._mapping) for r in db.execute(
            text("select id, bukrs, kunnr, belnr, xblnr, vbeln, wrbtr, waers, shkzg, bldat, zfbdt, xref2 from sap.bsid "
                 "where id = any(:ids)"), {"ids": [c.bsid_id for c in cands]})}
    audit = db.scalars(select(AuditLog).where(
        or_(and_(AuditLog.entity_type == "work_item", AuditLog.entity_id == w.entry_id),
            and_(AuditLog.entity_type == "email", AuditLog.entity_id == e.email_ref)))
        .order_by(AuditLog.occurred_at, AuditLog.id)).all()
    siblings = db.execute(select(WorkItem, EmailMessage).join(EmailMessage, EmailMessage.id == WorkItem.email_id)
                          .where(WorkItem.email_id == e.id, WorkItem.id != w.id).order_by(WorkItem.line_no)).all()
    ptp = db.scalars(select(PtpCommitment).where(PtpCommitment.work_item_id == w.id)).all()

    body = summary(w, e, user, rates, original.entry_id if original else None)
    body.update({
        "work_item": columns(w),
        "email": columns(e, exclude=("raw_uri", "body_layout", "gmail_id", "thread_id")),
        "attachments": attachments,
        "classification_detail": columns(cls) if cls else None,
        "extraction": columns(ext) if ext else None,
        "extraction_line": columns(line) if line else None,
        "evidence": w.extraction_evidence,
        "candidates": [{**columns(c), "bsid_item": items.get(c.bsid_id)} for c in cands],
        "score_breakdown": {k: getattr(w, k) for k in (
            "invoice_match_score", "amount_alignment_score", "sender_company_score", "customer_name_similarity",
            "date_proxy_score", "raw_score", "confidence_score", "confidence_category", "confidence_source",
            "formula_confidence", "fast_path_override", "amount_difference_pct", "date_difference_days",
            "payer_cluster_flag", "currency_cluster_flag")},
        "ptp_commitments": [columns(p) for p in ptp],
        "same_email_items": [summary(s, se, user, rates) for s, se in siblings],
        "audit": [columns(a) for a in audit],
    })
    return jsonable_encoder(body)


# --------------------------------------------------------------------------- attachments
@router.get("/attachments/{attachment_id}/file", summary="Attachment file (signed short-lived link, no auth header needed)")
def attachment_file(attachment_id: int, token: str, db: Session = Depends(get_db)):
    claims = read_token(token, "file")
    if claims.get("att") != attachment_id:
        raise HTTPException(401, "This link is for a different file.")
    a = db.get(EmailAttachment, attachment_id)
    if a is None:
        raise HTTPException(404, "Attachment not found")
    mime = a.mime_type or mimetypes.guess_type(a.filename)[0] or "application/octet-stream"
    inline = mime in INLINE_TYPES  # HTML, SVG, XML and the like are only ever downloaded, never shown by the browser
    headers = {"Content-Disposition": f'{"inline" if inline else "attachment"}; filename="{a.filename.encode("ascii", "replace").decode()}"',
               "X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=300",
               "Content-Security-Policy": "sandbox"}
    return Response(get_storage().get(a.storage_uri), media_type=mime if inline else "application/octet-stream", headers=headers)


@router.get("/attachments/{attachment_id}/layout", summary="Words with positions + tables of an attachment (evidence highlighting)")
def attachment_layout(attachment_id: int, user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    a = db.get(EmailAttachment, attachment_id)
    if a is None:
        raise HTTPException(404, "Attachment not found")
    return jsonable_encoder({"id": a.id, "filename": a.filename, "page_count": a.page_count,
                             "parse_method": a.parse_method, "text": a.text_content, "layout": a.layout})


# --------------------------------------------------------------------------- change feed (replaces a live stream)
@router.get("/changes", summary="What changed since a time - poll every 15-20 s while the tab is visible")
def changes(since: datetime, user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    """Counts and ids of new / updated rows. Use `next_since` of the answer as the next `since`.
    `next_since` is the server time minus 60 s: a row written by a transaction that started before the poll but
    committed after it would otherwise be missed. (Ids repeat for a minute; harmless.)
    No connection is kept open, so the Container App can still scale to zero."""
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    now = db.scalar(select(func.now()))
    new_ids = db.scalars(select(WorkItem.id).where(WorkItem.created_at > since).order_by(WorkItem.id).limit(200)).all()
    new_n = db.scalar(select(func.count()).select_from(WorkItem).where(WorkItem.created_at > since))
    upd_ids = db.scalars(select(WorkItem.id).where(WorkItem.updated_at > since, WorkItem.created_at <= since)
                         .order_by(WorkItem.id).limit(200)).all()
    upd_n = db.scalar(select(func.count()).select_from(WorkItem)
                      .where(WorkItem.updated_at > since, WorkItem.created_at <= since))
    emails = db.scalar(select(func.count()).select_from(EmailMessage).where(EmailMessage.created_at > since))
    return {"server_time": now, "next_since": now - timedelta(seconds=CHANGES_OVERLAP_S), "since": since,
            "new_work_items": {"count": new_n, "ids": new_ids},
            "updated_work_items": {"count": upd_n, "ids": upd_ids},
            "new_emails": emails, "changed": bool(new_n or upd_n or emails)}
