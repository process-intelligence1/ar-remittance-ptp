"""Outbound e-mail (M09): clarification requests written from templates in the customer's language.

SAFETY (CLAUDE.md rule 3): in this demo every outgoing e-mail goes ONLY to OUTBOUND_REDIRECT_TO. The customer it is
meant for is named in the subject and at the top of the body: `[AR-DEMO][<KIND> → <intended recipient>] ...`.
The analyst sees the rendered text first (preview), may edit it, and only then is it queued. The worker sends it
(job SEND_EMAIL) through the Gmail API with header `X-AR-Demo: outbound` and the label AR-Outbound.
"""
import base64
from datetime import datetime, timezone
from email.message import EmailMessage as MimeMessage

from jinja2 import Environment, StrictUndefined
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import jobs
from app.config import get_settings
from app.models.ar import AuditLog, EmailMessage, OutboundMessage, WorkItem

SEND_EMAIL = "SEND_EMAIL"
DEMO_HEADER = "X-AR-Demo"
KIND_CLARIFICATION = "CLARIFICATION"

# KNA1.SPRAS (SAP language key) -> template language
LANGUAGES = {"E": "en", "D": "de", "F": "fr", "S": "es", "P": "pt", "J": "ja"}

_env = Environment(autoescape=False, undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)

# {{ detail }} = one line describing the payment ("invoice 123, USD 1,000.00"); {{ question }} = the analyst's own words.
TEMPLATES = {
    "en": {"subject": "Clarification needed: {{ detail }}",
           "body": "Dear {{ customer }},\n\nthank you for your payment information. Before we can apply it we need a clarification "
                   "regarding {{ detail }}:\n\n{{ question }}\n\nPlease reply to this e-mail.\n\nKind regards\nAccounts Receivable"},
    "de": {"subject": "Rückfrage: {{ detail }}",
           "body": "Sehr geehrte Damen und Herren ({{ customer }}),\n\nvielen Dank für Ihre Zahlungsinformation. Bevor wir sie "
                   "verbuchen können, benötigen wir eine Klärung zu {{ detail }}:\n\n{{ question }}\n\nBitte antworten Sie auf "
                   "diese E-Mail.\n\nMit freundlichen Grüßen\nDebitorenbuchhaltung"},
    "fr": {"subject": "Demande de précisions : {{ detail }}",
           "body": "Madame, Monsieur ({{ customer }}),\n\nmerci pour votre avis de paiement. Avant de pouvoir l'affecter, nous avons "
                   "besoin d'une précision concernant {{ detail }} :\n\n{{ question }}\n\nMerci de répondre à ce message.\n\n"
                   "Cordialement\nComptabilité clients"},
    "es": {"subject": "Aclaración necesaria: {{ detail }}",
           "body": "Estimados señores ({{ customer }}):\n\ngracias por la información de su pago. Antes de aplicarlo necesitamos una "
                   "aclaración sobre {{ detail }}:\n\n{{ question }}\n\nPor favor, responda a este correo.\n\nSaludos cordiales\n"
                   "Cuentas por cobrar"},
    "pt": {"subject": "Esclarecimento necessário: {{ detail }}",
           "body": "Prezados senhores ({{ customer }}),\n\nobrigado pelas informações do pagamento. Antes de aplicá-lo precisamos de "
                   "um esclarecimento sobre {{ detail }}:\n\n{{ question }}\n\nPor favor, responda a este e-mail.\n\nAtenciosamente\n"
                   "Contas a receber"},
    "ja": {"subject": "ご確認のお願い：{{ detail }}",
           "body": "{{ customer }} ご担当者様\n\nお支払いのご連絡をありがとうございます。消込の前に、{{ detail }} について"
                   "ご確認をお願いいたします。\n\n{{ question }}\n\nこのメールにご返信ください。\n\nよろしくお願いいたします。\n売掛金管理"},
}

DEFAULT_QUESTION = {
    "en": "Could you please confirm the invoice number(s) and the amount this payment is meant for?",
    "de": "Könnten Sie bitte die Rechnungsnummer(n) und den Betrag bestätigen, für die diese Zahlung gedacht ist?",
    "fr": "Pourriez-vous confirmer le ou les numéros de facture et le montant concernés par ce paiement ?",
    "es": "¿Podría confirmar el número o números de factura y el importe al que corresponde este pago?",
    "pt": "Poderia confirmar o(s) número(s) da fatura e o valor a que este pagamento se refere?",
    "ja": "このお支払いの対象となる請求書番号と金額をご確認いただけますでしょうか。",
}


class OutboundError(RuntimeError):
    pass


def language_for(db: Session, kunnr: str | None) -> str:
    spras = db.scalar(text("select spras from sap.kna1 where kunnr = :k"), {"k": kunnr}) if kunnr else None
    return LANGUAGES.get((spras or "").upper(), "en")


def _money(w: WorkItem) -> str:
    return f"{w.currency or ''} {w.amount:,.2f}".strip() if w.amount is not None else ""


def render_clarification(db: Session, w: WorkItem, e: EmailMessage, question: str | None = None) -> dict:
    """The e-mail the analyst will see: subject, body, language and who it is really meant for."""
    s = get_settings()
    lang = language_for(db, w.kunnr)
    detail = ", ".join(x for x in (f"invoice {w.invoice_ref_raw}" if w.invoice_ref_raw else "your payment", _money(w)) if x)
    ctx = {"customer": w.customer_name or e.sender_name or "customer", "detail": detail,
           "question": (question or "").strip() or DEFAULT_QUESTION[lang]}
    tpl = TEMPLATES[lang]
    intended = e.sender_email or "(unknown sender)"
    subject = f"[AR-DEMO][{KIND_CLARIFICATION} → {intended}] " + _env.from_string(tpl["subject"]).render(**ctx)
    body = (f"[AR-DEMO] In production this e-mail would go to {intended}. Demo mode: it is delivered to {s.outbound_redirect_to} only.\n\n"
            + _env.from_string(tpl["body"]).render(**ctx))
    return {"subject": subject, "body": body, "language": lang, "intended_recipient": intended,
            "actual_recipient": s.outbound_redirect_to, "template": f"{KIND_CLARIFICATION.lower()}_{lang}"}


def queue_message(db: Session, w: WorkItem, e: EmailMessage, *, subject: str, body: str, created_by: str,
                  kind: str = KIND_CLARIFICATION, intended: str | None = None) -> OutboundMessage:
    """Store the (possibly edited) e-mail and queue the send job. The recipient is ALWAYS the redirect address.
    `intended` = who it would go to in production (default: the customer; internal alerts name a role)."""
    s = get_settings()
    if s.outbound_mode != "redirect":
        raise OutboundError("OUTBOUND_MODE must be 'redirect' - the demo never e-mails real customers.")
    subject, body = (subject or "").strip(), (body or "").strip()
    if not subject or not body:
        raise OutboundError("The e-mail needs a subject and a text.")
    lang = language_for(db, w.kunnr) if kind == KIND_CLARIFICATION else "en"  # internal alerts are always English
    msg = OutboundMessage(work_item_id=w.id, email_id=e.id, kind=kind, intended_recipient=intended or e.sender_email,
                          actual_recipient=s.outbound_redirect_to, subject=subject, body=body, language=lang,
                          template=f"{kind.lower()}_{lang}", status="QUEUED", created_by=created_by)
    db.add(msg)
    db.flush()
    jobs.enqueue(db, SEND_EMAIL, {"outbound_id": msg.id})
    return msg


def build_mime(msg: OutboundMessage, in_reply_to: str | None = None) -> MimeMessage:
    s = get_settings()
    mime = MimeMessage()
    mime["To"] = s.outbound_redirect_to  # never msg.intended_recipient
    mime["Subject"] = msg.subject
    mime[DEMO_HEADER] = "outbound"
    if in_reply_to:
        mime["In-Reply-To"] = in_reply_to
        mime["References"] = in_reply_to
    mime.set_content(msg.body)
    return mime


def send_message(db: Session, msg: OutboundMessage, service=None) -> OutboundMessage:
    """Send one queued e-mail through Gmail (worker). Marks it SENT, or FAILED with the reason, and re-raises on failure
    so the job is retried."""
    from app.gmail.client import build_service, ensure_label

    s = get_settings()
    if s.outbound_mode != "redirect":
        raise OutboundError("OUTBOUND_MODE must be 'redirect'.")
    if msg.status == "SENT":
        return msg
    email = db.get(EmailMessage, msg.email_id) if msg.email_id else None
    try:
        service = service or build_service()
        threaded = bool(email) and msg.kind == KIND_CLARIFICATION  # only a clarification joins the customer's e-mail thread
        mime = build_mime(msg, email.rfc_message_id if threaded else None)
        body = {"raw": base64.urlsafe_b64encode(mime.as_bytes()).decode()}
        if threaded and email.thread_id:
            body["threadId"] = email.thread_id
        sent = service.users().messages().send(userId="me", body=body).execute()
        label_id = ensure_label(service, s.gmail_outbound_label)
        service.users().messages().modify(userId="me", id=sent["id"], body={"addLabelIds": [label_id]}).execute()
    except Exception as exc:
        msg.status, msg.error = "FAILED", f"{type(exc).__name__}: {exc}"[:500]
        db.commit()
        raise
    msg.status, msg.error = "SENT", None
    msg.gmail_message_id = sent.get("id")
    msg.gmail_thread_id = sent.get("threadId") or (email.thread_id if threaded else None)
    msg.sent_at = datetime.now(timezone.utc)
    db.commit()
    return msg


def send_queued(db: Session, budget: int = 20) -> tuple[int, int]:
    """Worker step: send the SEND_EMAIL jobs that are due. Returns (sent, failed)."""
    sent = failed = 0
    for _ in range(budget):
        job = jobs.claim_next(db, SEND_EMAIL)
        if job is None:
            break
        try:
            msg = db.get(OutboundMessage, (job.payload or {}).get("outbound_id"))
            if msg is None:
                raise LookupError("outbound message not found")
            send_message(db, msg)
            jobs.complete(db, job)
            sent += 1
        except Exception as exc:
            db.rollback()
            jobs.fail(db, job, f"{type(exc).__name__}: {exc}")
            failed += 1
    return sent, failed


def attach_reply(db: Session, reply: EmailMessage) -> EmailMessage | None:
    """A customer reply (same Gmail thread as an e-mail we sent) belongs to the case it answers: link it, and put the
    case's rows that were AWAITING_CUSTOMER back into review. The reply itself is processed like any other e-mail
    (the worker queues it), so corrected numbers or attachments in it are read and matched. Caller commits."""
    parent_id = thread_case(db, reply.thread_id)
    if parent_id is None or parent_id == reply.id:
        return None
    parent = db.get(EmailMessage, parent_id)
    reply.parent_email_id = parent.id
    for w in db.scalars(select(WorkItem).where(WorkItem.email_id == parent.id, WorkItem.status == "AWAITING_CUSTOMER")):
        w.status = "PENDING_REVIEW"
        db.add(AuditLog(business_date=reply.business_date, actor="system", entity_type="work_item", entity_id=w.entry_id,
                        action="CUSTOMER_REPLIED",
                        details={"before": {"status": "AWAITING_CUSTOMER"}, "after": {"status": "PENDING_REVIEW"},
                                 "reply_email": reply.email_ref, "reply_from": reply.sender_email}))
    db.add(AuditLog(business_date=reply.business_date, actor="system", entity_type="email", entity_id=parent.email_ref,
                    action="CUSTOMER_REPLY_ATTACHED", details={"reply_email": reply.email_ref}))
    return parent


def thread_case(db: Session, thread_id: str | None) -> int | None:
    """The e-mail a reply belongs to: the one an outbound message was sent about, found by Gmail thread."""
    if not thread_id:
        return None
    return db.scalar(select(OutboundMessage.email_id).where(OutboundMessage.gmail_thread_id == thread_id,
                                                            OutboundMessage.status == "SENT").limit(1))
