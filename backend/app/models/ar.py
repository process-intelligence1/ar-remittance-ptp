"""Application tables (schema "ar") - everything the app itself creates.

Flow of data through these tables:

  email_message ──< email_attachment
        │
        ├── email_classification         (Remittance / PTP / Out of Scope)
        │
        └──< work_item  (ONE ROW PER INVOICE)  ──< match_candidate  (BSID candidates + scores)
                   │                          ──< ptp_commitment   (promise dates / instalments)
                   │                          ──< outbound_message (clarifications, alerts)
                   └── audit_log (every action on every row, append-only)

Supporting tables: job (background work queue), rule_config (tunable rules),
app_user (demo users and roles).
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

SCHEMA = "ar"
AR = {"schema": SCHEMA}


def _created():
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# --------------------------------------------------------------------------- e-mail
class EmailMessage(Base):
    """One incoming e-mail (from Gmail, the sample library, or an upload)."""
    __tablename__ = "email_message"
    __table_args__ = (Index("ix_email_sender_domain", "sender_domain"), AR)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email_ref: Mapped[str] = mapped_column(String(20), unique=True)  # e.g. EML-000001
    source: Mapped[str] = mapped_column(String(20))  # gmail | sample | upload | history
    gmail_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    rfc_message_id: Mapped[str | None] = mapped_column(String(300))
    thread_id: Mapped[str | None] = mapped_column(String(64))
    sample_code: Mapped[str | None] = mapped_column(String(20))  # e.g. R01-0007
    from_email: Mapped[str | None] = mapped_column(String(200))  # real From: header (the forwarder, if forwarded)
    is_forwarded: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    sender_email: Mapped[str | None] = mapped_column(String(200))  # original sender (taken from the forward block)
    sender_name: Mapped[str | None] = mapped_column(String(200))
    sender_domain: Mapped[str | None] = mapped_column(String(120))
    subject: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    business_date: Mapped[date | None] = mapped_column(Date)
    body_text: Mapped[str | None] = mapped_column(Text)
    body_text_clean: Mapped[str | None] = mapped_column(Text)  # quoted replies removed
    body_layout: Mapped[dict | None] = mapped_column(JSONB)  # tables found in the body (HTML or aligned text)
    raw_uri: Mapped[str | None] = mapped_column(String(500))  # where the .eml is stored
    sha256: Mapped[str | None] = mapped_column(String(64))
    language: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="NEW")  # NEW | PARSED | CLASSIFIED | PROCESSED | FAILED | SKIPPED
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()


class EmailAttachment(Base):
    """A file attached to an e-mail (files inside a ZIP point to the ZIP via parent_id)."""
    __tablename__ = "email_attachment"
    __table_args__ = (Index("ix_email_attachment_sha256", "sha256"), AR)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.email_message.id", ondelete="CASCADE"))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SCHEMA}.email_attachment.id"))
    filename: Mapped[str] = mapped_column(String(300))
    mime_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64))
    storage_uri: Mapped[str | None] = mapped_column(String(500))
    is_inline: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))  # e.g. logo in the body
    depth: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))  # 0 = attached, 1+ = inside a ZIP
    page_count: Mapped[int | None] = mapped_column(Integer)
    parse_method: Mapped[str | None] = mapped_column(String(20))  # text | ocr | mixed | docx | spreadsheet | csv | container | unsupported
    parse_status: Mapped[str] = mapped_column(String(20), default="PENDING", server_default=text("'PENDING'"))  # PENDING | PARSED | FAILED | SKIPPED
    parse_error: Mapped[str | None] = mapped_column(Text)
    parse_reused: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))  # copied from an identical file (same SHA-256)
    parse_ms: Mapped[int | None] = mapped_column(Integer)  # time the original parse took
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    text_content: Mapped[str | None] = mapped_column(Text)
    layout: Mapped[dict | None] = mapped_column(JSONB)  # words/tables with page + bounding boxes
    ocr_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    language: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = _created()


class EmailClassification(Base):
    """What kind of e-mail it is, decided when the e-mail is read."""
    __tablename__ = "email_classification"
    __table_args__ = (Index("ix_email_classification_current", "email_id", "is_current"), AR)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.email_message.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(20))  # REMITTANCE | PTP | OUT_OF_SCOPE
    contains_remittance: Mapped[bool] = mapped_column(Boolean, default=False)
    contains_ptp: Mapped[bool] = mapped_column(Boolean, default=False)
    out_of_scope_category: Mapped[str | None] = mapped_column(String(60))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    method: Mapped[str | None] = mapped_column(String(20))  # rules | rules+model | manual
    reasons: Mapped[dict | None] = mapped_column(JSONB)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _created()


# --------------------------------------------------------------------------- invoice rows
class Extraction(Base):
    """What was read from an e-mail (M04): one header per run; older runs kept (is_current = false)."""
    __tablename__ = "extraction"
    __table_args__ = (Index("ix_extraction_current", "email_id", "is_current"), AR)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.email_message.id", ondelete="CASCADE"))
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20))  # OK | PARTIAL | NO_LINES | SKIPPED
    method: Mapped[str] = mapped_column(String(20), default="rules")  # rules | rules+llm (optional fallback)
    payer_name: Mapped[str | None] = mapped_column(String(200))
    sender_domain: Mapped[str | None] = mapped_column(String(120))
    customer_number: Mapped[str | None] = mapped_column(String(20))   # as quoted by the payer
    payer_account: Mapped[str | None] = mapped_column(String(40))     # IBAN (valid check digits) or account no.
    our_reference: Mapped[str | None] = mapped_column(String(60))
    your_reference: Mapped[str | None] = mapped_column(String(60))
    payment_reference: Mapped[str | None] = mapped_column(String(60))
    advice_number: Mapped[str | None] = mapped_column(String(60))
    remittance_refs: Mapped[list | None] = mapped_column(JSONB)        # REM-...
    payment_date: Mapped[date | None] = mapped_column(Date)
    promise_date: Mapped[date | None] = mapped_column(Date)
    promise_text: Mapped[str | None] = mapped_column(String(200))      # the wording, e.g. "end of month"
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(17, 3))
    payment_currency: Mapped[str | None] = mapped_column(String(3))
    fx_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))    # as stated; nothing is converted
    document_currency: Mapped[str | None] = mapped_column(String(3))
    lines_count: Mapped[int] = mapped_column(Integer, default=0)
    lines_sum: Mapped[Decimal | None] = mapped_column(Numeric(17, 3))
    total_mismatch: Mapped[Decimal | None] = mapped_column(Numeric(17, 3))  # total - sum of remittance lines
    warnings: Mapped[list | None] = mapped_column(JSONB)
    evidence: Mapped[dict | None] = mapped_column(JSONB)              # where each header value was found
    created_at: Mapped[datetime] = _created()


class ExtractionLine(Base):
    """One invoice (or instalment) read from an e-mail; M05 turns these into ar.work_item rows."""
    __tablename__ = "extraction_line"
    __table_args__ = (Index("ix_extraction_line_ref", "invoice_ref_norm"), AR)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    extraction_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.extraction.id", ondelete="CASCADE"))
    line_no: Mapped[int] = mapped_column(Integer)
    line_type: Mapped[str] = mapped_column(String(12))   # REMITTANCE | PTP
    invoice_ref_raw: Mapped[str] = mapped_column(String(60))
    invoice_ref_norm: Mapped[str | None] = mapped_column(String(60))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(17, 3))           # net paid / promised (credit < 0)
    gross_amount: Mapped[Decimal | None] = mapped_column(Numeric(17, 3))
    deduction_amount: Mapped[Decimal | None] = mapped_column(Numeric(17, 3))
    deduction_reason: Mapped[str | None] = mapped_column(String(120))        # TDS, bank charges, ...
    line_currency: Mapped[str | None] = mapped_column(String(3))             # the invoice's, when stated
    payment_currency: Mapped[str | None] = mapped_column(String(3))
    fx_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    credit_note_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    invoice_date: Mapped[date | None] = mapped_column(Date)
    promise_date: Mapped[date | None] = mapped_column(Date)
    promise_text: Mapped[str | None] = mapped_column(String(200))
    instalment_no: Mapped[int | None] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(String(20))      # table | text_line | prose | mention | instalment
    source_kind: Mapped[str | None] = mapped_column(String(20))  # body | pdf_text | ocr | xlsx | docx | csv | other
    source_name: Mapped[str | None] = mapped_column(String(300))
    attachment_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SCHEMA}.email_attachment.id", ondelete="SET NULL"))
    evidence: Mapped[dict | None] = mapped_column(JSONB)


class WorkItem(Base):
    """ONE ROW PER INVOICE referenced in an e-mail - the rows of the Action Queue.

    final_classification: REMITTANCE | PTP | DUPLICATE | EXCEPTION | OUT_OF_SCOPE
    status:               AUTO_PROCESSED | PENDING_REVIEW | EXCEPTION | DUPLICATE |
                          CONFIRMED | RESOLVED | REJECTED | IGNORED
    """
    __tablename__ = "work_item"
    __table_args__ = (
        Index("ix_work_item_status", "status"),
        Index("ix_work_item_kunnr", "kunnr"),
        Index("ix_work_item_invoice_ref_norm", "invoice_ref_norm"),
        Index("ix_work_item_email_id", "email_id"),
        Index("ix_work_item_bukrs", "bukrs"),
        Index("ix_work_item_region", "region"),
        Index("ix_work_item_updated_at", "updated_at"),
        Index("ix_work_item_created_at", "created_at"),
        AR,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entry_id: Mapped[str] = mapped_column(String(20), unique=True)  # ENT-000001
    email_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.email_message.id", ondelete="CASCADE"))
    line_no: Mapped[int] = mapped_column(Integer, default=1)
    line_type: Mapped[str | None] = mapped_column(String(20))  # REMITTANCE | PTP | None for out of scope
    final_classification: Mapped[str] = mapped_column(String(20))

    # --- extracted from the e-mail ---
    customer_name: Mapped[str | None] = mapped_column(String(200))
    kunnr: Mapped[str | None] = mapped_column(String(10))
    bukrs: Mapped[str | None] = mapped_column(String(4))
    invoice_ref_raw: Mapped[str | None] = mapped_column(String(60))
    invoice_ref_norm: Mapped[str | None] = mapped_column(String(60))
    invoice_date: Mapped[date | None] = mapped_column(Date)
    remittance_ref: Mapped[str | None] = mapped_column(String(60))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(17, 3))
    currency: Mapped[str | None] = mapped_column(String(3))
    payment_date: Mapped[date | None] = mapped_column(Date)
    promise_date: Mapped[date | None] = mapped_column(Date)
    deduction_amount: Mapped[Decimal | None] = mapped_column(Numeric(17, 3))
    deduction_reason: Mapped[str | None] = mapped_column(String(120))
    credit_note_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    body_only_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    multi_attachment_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    extraction_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    extraction_evidence: Mapped[dict | None] = mapped_column(JSONB)  # where each value was found

    # --- BSID match and scoring (Knowledge Base formula) ---
    bsid_id: Mapped[int | None] = mapped_column(BigInteger)  # sap.bsid.id of the matched open item (BSID/BSAD are never changed by the app)
    bsid_match_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    region: Mapped[str | None] = mapped_column(String(20))  # BSID XREF2 of the matched item (kept after clearing)
    bsid_open_item_status: Mapped[str | None] = mapped_column(String(20))  # OPEN | PARTIALLY_OPEN | CLEARED
    match_type: Mapped[str | None] = mapped_column(String(40))
    match_field: Mapped[str | None] = mapped_column(String(10))  # XBLNR | BELNR | VBELN
    match_level: Mapped[str | None] = mapped_column(String(10))  # EXACT | NEAR | NONE
    invoice_match_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    amount_difference_pct: Mapped[Decimal | None] = mapped_column(Numeric(9, 4))
    amount_alignment_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    sender_company_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    customer_name_similarity: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    date_difference_days: Mapped[int | None] = mapped_column(Integer)
    date_proxy_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    payer_cluster_flag: Mapped[bool | None] = mapped_column(Boolean)
    currency_cluster_flag: Mapped[bool | None] = mapped_column(Boolean)
    raw_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    confidence_category: Mapped[str | None] = mapped_column(String(10))  # HIGH | MEDIUM | LOW
    fast_path_override: Mapped[str | None] = mapped_column(String(60))
    # M05: confidence = max(fast-path value, formula); which one won, and the formula value itself
    confidence_source: Mapped[str | None] = mapped_column(String(12))  # FAST_PATH | FORMULA
    formula_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    review_reasons: Mapped[list | None] = mapped_column(JSONB)  # why a high score still goes to review
    # M05: who is paying, and how that was decided
    extraction_line_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.extraction_line.id", ondelete="SET NULL"))
    customer_match_method: Mapped[str | None] = mapped_column(String(20))  # INVOICE | SENDER_ADDRESS | ...
    customer_match_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    customer_evidence: Mapped[dict | None] = mapped_column(JSONB)

    # --- decision and workflow ---
    decision: Mapped[str | None] = mapped_column(String(30))  # AUTO_PROCESS | MANUAL_REVIEW | MANUAL_INVESTIGATION | EXCEPTION | DUPLICATE | OUT_OF_SCOPE
    status: Mapped[str] = mapped_column(String(20), default="PENDING_REVIEW")
    exception_reason: Mapped[str | None] = mapped_column(String(200))
    out_of_scope_reason: Mapped[str | None] = mapped_column(String(200))
    duplicate_of_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SCHEMA}.work_item.id"))
    recommended_action: Mapped[str | None] = mapped_column(String(120))
    assigned_role: Mapped[str | None] = mapped_column(String(40))
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    run_id: Mapped[str | None] = mapped_column(String(40))
    execution_ms: Mapped[int | None] = mapped_column(Integer)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MatchCandidate(Base):
    """Every BSID item considered for a row, with its score - shown as 'why this match'."""
    __tablename__ = "match_candidate"
    __table_args__ = (AR,)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    work_item_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.work_item.id", ondelete="CASCADE"))
    bsid_id: Mapped[int] = mapped_column(BigInteger)
    rank: Mapped[int] = mapped_column(Integer)
    scores: Mapped[dict] = mapped_column(JSONB)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    chosen: Mapped[bool] = mapped_column(Boolean, default=False)


class PtpCommitment(Base):
    """A customer's promise to pay one invoice (one row per instalment)."""
    __tablename__ = "ptp_commitment"
    __table_args__ = (Index("ix_ptp_status_date", "status", "promise_date"), AR)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    work_item_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.work_item.id", ondelete="CASCADE"))
    kunnr: Mapped[str | None] = mapped_column(String(10))
    bukrs: Mapped[str | None] = mapped_column(String(4))
    bsid_id: Mapped[int | None] = mapped_column(BigInteger)
    instalment_no: Mapped[int] = mapped_column(Integer, default=1)
    promise_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(17, 3))
    currency: Mapped[str | None] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(20), default="OPEN")  # OPEN | KEPT | PARTIALLY_KEPT | BROKEN | CANCELLED
    amount_received: Mapped[Decimal | None] = mapped_column(Numeric(17, 3))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()


# --------------------------------------------------------------------------- actions
class OutboundMessage(Base):
    """E-mails the app sends. In demo mode they all go to the redirect address."""
    __tablename__ = "outbound_message"
    __table_args__ = (AR,)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    work_item_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SCHEMA}.work_item.id", ondelete="SET NULL"))
    email_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SCHEMA}.email_message.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(30))  # CLARIFICATION | ESCALATION | PTP_REMINDER | DUPLICATE_NOTICE | ALERT
    intended_recipient: Mapped[str | None] = mapped_column(String(200))
    actual_recipient: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    gmail_message_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")  # DRAFT | SENT | FAILED
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = _created()


class AuditLog(Base):
    """Append-only history of everything that happened (system and users)."""
    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"), Index("ix_audit_occurred_at", "occurred_at"),
                      Index("ix_audit_actor", "actor"), AR)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    occurred_at: Mapped[datetime] = _created()
    business_date: Mapped[date | None] = mapped_column(Date)
    actor: Mapped[str] = mapped_column(String(120))  # user e-mail or "system"
    actor_role: Mapped[str | None] = mapped_column(String(40))
    entity_type: Mapped[str] = mapped_column(String(30))  # work_item | email | ptp | rule | demo
    entity_id: Mapped[str | None] = mapped_column(String(40))
    action: Mapped[str] = mapped_column(String(60))
    details: Mapped[dict | None] = mapped_column(JSONB)  # before / after values, reason, etc.
    run_id: Mapped[str | None] = mapped_column(String(40))


# --------------------------------------------------------------------------- platform
class Job(Base):
    """Simple background work queue kept in PostgreSQL (retries + 're-process' button)."""
    __tablename__ = "job"
    __table_args__ = (Index("ix_job_status_run_after", "status", "run_after"), AR)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    job_type: Mapped[str] = mapped_column(String(40))  # POLL_GMAIL | PROCESS_EMAIL | PTP_FOLLOWUP | SEND_EMAIL
    payload: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="QUEUED")  # QUEUED | RUNNING | DONE | FAILED
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RuleConfig(Base):
    """Tunable business rules (weights, thresholds, tolerances) - editable by the AR Supervisor."""
    __tablename__ = "rule_config"
    __table_args__ = (AR,)

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB)
    description: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[str | None] = mapped_column(String(120))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AppUser(Base):
    """Demo users and their roles."""
    __tablename__ = "app_user"
    __table_args__ = (AR,)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(40))  # AR_ANALYST | CASH_APPLICATION | COLLECTIONS_ANALYST | AR_SUPERVISOR
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _created()
