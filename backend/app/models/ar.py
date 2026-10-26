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
    sender_email: Mapped[str | None] = mapped_column(String(200))
    sender_name: Mapped[str | None] = mapped_column(String(200))
    sender_domain: Mapped[str | None] = mapped_column(String(120))
    subject: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    business_date: Mapped[date | None] = mapped_column(Date)
    body_text: Mapped[str | None] = mapped_column(Text)
    body_text_clean: Mapped[str | None] = mapped_column(Text)  # quoted replies removed
    raw_uri: Mapped[str | None] = mapped_column(String(500))  # where the .eml is stored
    sha256: Mapped[str | None] = mapped_column(String(64))
    language: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="NEW")  # NEW | PARSED | CLASSIFIED | PROCESSED | FAILED | SKIPPED
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()


class EmailAttachment(Base):
    """A file attached to an e-mail (files inside a ZIP point to the ZIP via parent_id)."""
    __tablename__ = "email_attachment"
    __table_args__ = (AR,)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.email_message.id", ondelete="CASCADE"))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SCHEMA}.email_attachment.id"))
    filename: Mapped[str] = mapped_column(String(300))
    mime_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64))
    storage_uri: Mapped[str | None] = mapped_column(String(500))
    page_count: Mapped[int | None] = mapped_column(Integer)
    parse_method: Mapped[str | None] = mapped_column(String(20))  # text | ocr | native_table
    text_content: Mapped[str | None] = mapped_column(Text)
    layout: Mapped[dict | None] = mapped_column(JSONB)  # words/tables with page + bounding boxes
    ocr_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    language: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = _created()


class EmailClassification(Base):
    """What kind of e-mail it is, decided when the e-mail is read."""
    __tablename__ = "email_classification"
    __table_args__ = (AR,)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.email_message.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(20))  # REMITTANCE | PTP | OUT_OF_SCOPE
    contains_remittance: Mapped[bool] = mapped_column(Boolean, default=False)
    contains_ptp: Mapped[bool] = mapped_column(Boolean, default=False)
    out_of_scope_category: Mapped[str | None] = mapped_column(String(60))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    method: Mapped[str | None] = mapped_column(String(20))  # rules | model | manual
    reasons: Mapped[dict | None] = mapped_column(JSONB)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _created()


# --------------------------------------------------------------------------- invoice rows
class WorkItem(Base):
    """ONE ROW PER INVOICE referenced in an e-mail - the rows of the Action Queue.

    final_classification: REMITTANCE | PTP | DUPLICATE | EXCEPTION | OUT_OF_SCOPE
    status:               AUTO_PROCESSED | PENDING_REVIEW | EXCEPTION | DUPLICATE |
                          RESOLVED | REJECTED | IGNORED
    """
    __tablename__ = "work_item"
    __table_args__ = (
        Index("ix_work_item_status", "status"),
        Index("ix_work_item_kunnr", "kunnr"),
        Index("ix_work_item_invoice_ref_norm", "invoice_ref_norm"),
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
    bsid_id: Mapped[int | None] = mapped_column(BigInteger)  # sap.bsid.id or sap.bsad.id after clearing
    bsid_match_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    bsid_open_item_status: Mapped[str | None] = mapped_column(String(20))  # OPEN | PARTIALLY_OPEN | CLEARED
    match_type: Mapped[str | None] = mapped_column(String(40))
    digit_match_length: Mapped[int | None] = mapped_column(Integer)
    digit_evidence_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
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
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"), AR)

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
