"""Classify a stored e-mail (after M02 reading) and save the result.

- Input: subject, clean body, text of every parsed attachment (inline logos skipped), sender.
- Output: a new current row in ar.email_classification (older rows kept, is_current = false),
  e-mail status PARSED -> CLASSIFIED, audit entry EMAIL_CLASSIFIED, and - for Gmail e-mails, when
  Gmail is used (Azure, or --gmail-labels on the laptop) - the label AR-Remittance / AR-PTP /
  AR-OutOfScope.
"""
import logging
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.classification.classifier import _NO_MODEL, classify
from app.classification.inputs import ClassifierInput, Document
from app.classification.rules import Classification
from app.config import get_settings
from app.gmail.parsing import domain_of
from app.gmail.poller import current_business_date
from app.models.ar import AuditLog, EmailAttachment, EmailClassification, EmailMessage, RuleConfig
from app.models.sap import Adr6
from app.rules_defaults import CLASSIFICATION

log = logging.getLogger(__name__)

CLASSIFIABLE = ("PARSED", "CLASSIFIED", "PROCESSED", "FAILED")
# Free-mail domains say nothing about the company behind the address
PUBLIC_DOMAINS = {"gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "yahoo.com", "icloud.com",
                  "live.com", "gmx.de", "web.de", "proton.me"}


class NotReadYet(Exception):
    """The e-mail's body and attachments have not been read (M02) yet."""


def rule_config(db: Session) -> dict:
    row = db.get(RuleConfig, "classification")
    return {**CLASSIFICATION, **(row.value if row and isinstance(row.value, dict) else {})}


def sender_known(db: Session, address: str | None) -> bool:
    """The address, or (for company domains) any address at the same domain, is in ADR6."""
    if not address:
        return False
    address = address.lower()
    if db.scalar(select(Adr6.id).where(func.lower(Adr6.smtp_addr) == address).limit(1)):
        return True
    domain = domain_of(address)
    if not domain or domain in PUBLIC_DOMAINS:
        return False
    return bool(db.scalar(select(Adr6.id).where(func.lower(Adr6.smtp_addr).like(f"%@{domain}")).limit(1)))


def input_for_email(db: Session, email: EmailMessage) -> ClassifierInput:
    atts = db.scalars(select(EmailAttachment).where(EmailAttachment.email_id == email.id,
                                                    EmailAttachment.is_inline.is_(False))
                      .order_by(EmailAttachment.id)).all()
    docs = [Document(a.filename, a.text_content or "") for a in atts if a.parse_status == "PARSED"]
    return ClassifierInput(
        subject=email.subject or "", body=email.body_text_clean or email.body_text or "", attachments=docs,
        sender_email=email.sender_email, sender_known=sender_known(db, email.sender_email),
        business_date=email.business_date or current_business_date(db))


def apply_gmail_label(email: EmailMessage, label: str, cfg: dict, service=None) -> str | None:
    """Put the classification label on the Gmail message (and take the other two off).
    Never raises: returns the label name, or None / an error text for the audit entry."""
    if not email.gmail_id:
        return None
    if service is None:
        if not get_settings().poller_enabled:  # laptop: Gmail belongs to Azure unless asked explicitly
            return None
        from app.gmail.client import build_service
        service = build_service()
    try:
        from app.gmail.client import ensure_label

        names = cfg["gmail_labels"]
        add = ensure_label(service, names[label])
        remove = [ensure_label(service, n) for k, n in names.items() if k != label]
        service.users().messages().modify(userId="me", id=email.gmail_id,
                                          body={"addLabelIds": [add], "removeLabelIds": remove}).execute()
        return names[label]
    except Exception as exc:  # labels are a convenience; the classification itself is saved
        log.warning("Gmail label for %s failed: %s", email.email_ref, exc)
        return f"label failed: {type(exc).__name__}"


def classify_email(db: Session, email: EmailMessage, gmail_service=None, model=_NO_MODEL) -> Classification:
    """model: omitted = the saved model; None = rules only (tests)."""
    if email.status not in CLASSIFIABLE or (email.status == "FAILED" and email.body_layout is None):
        raise NotReadYet(f"{email.email_ref} has not been read yet (status {email.status}) - run M02 first")
    cfg = rule_config(db)
    inp = input_for_email(db, email)
    result = classify(inp, cfg, model=model)

    db.execute(update(EmailClassification).where(EmailClassification.email_id == email.id,
                                                 EmailClassification.is_current.is_(True))
               .values(is_current=False))
    db.add(EmailClassification(
        email_id=email.id, label=result.label, contains_remittance=result.contains_remittance,
        contains_ptp=result.contains_ptp, out_of_scope_category=result.out_of_scope_category,
        confidence=Decimal(str(result.confidence)), method=result.method, reasons=result.reasons,
        is_current=True))
    if email.status == "PARSED":
        email.status = "CLASSIFIED"
    gmail_label = apply_gmail_label(email, result.label, cfg, gmail_service)
    db.add(AuditLog(business_date=current_business_date(db), actor="system", entity_type="email",
                    entity_id=email.email_ref, action="EMAIL_CLASSIFIED",
                    details={"label": result.label, "contains_remittance": result.contains_remittance,
                             "contains_ptp": result.contains_ptp, "category": result.out_of_scope_category,
                             "confidence": result.confidence, "method": result.method,
                             "gmail_label": gmail_label}))
    db.commit()
    return result


def current_classification(db: Session, email_id: int) -> EmailClassification | None:
    return db.scalar(select(EmailClassification).where(EmailClassification.email_id == email_id,
                                                       EmailClassification.is_current.is_(True)))
