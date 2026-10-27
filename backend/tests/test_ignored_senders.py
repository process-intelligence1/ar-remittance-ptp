"""Ignored system senders: matching, not storing during a poll, purging stored ones."""
from email.message import EmailMessage as Mime

import pytest
from sqlalchemy import select

from app.gmail.ignore import SenderIgnoreList, load_ignore_list
from app.gmail.poller import poll, store_email
from app.gmail.purge import find_ignored_emails, purge_emails
from app.gmail.sample_sender import build_message, load_sample
from app.models.ar import AuditLog, EmailAttachment, EmailMessage
from app.rules_defaults import IGNORED_SENDERS

RULES = SenderIgnoreList.from_value(IGNORED_SENDERS)


def _mail(frm: str, subject="Hello", body="text", attach: bytes | None = None) -> bytes:
    m = Mime()
    m["From"], m["To"], m["Subject"] = frm, "processintelligence1@gmail.com", subject
    m["Date"] = "Tue, 27 Oct 2026 08:00:00 +0000"
    m.set_content(body)
    if attach:
        m.add_attachment(attach, maintype="application", subtype="pdf", filename="receipt.pdf")
    return m.as_bytes()


@pytest.mark.parametrize("address,rule", [
    ("notifications@github.com", "domain github.com"),
    ("noreply-accounts@google.com", "domain google.com"),
    ("account-security-noreply@accountprotection.microsoft.com", "domain microsoft.com"),
    ("no-reply-abc@mail.anthropic.com", "domain anthropic.com"),
    ("billing@claude.ai", "domain claude.ai"),
    ("NoReply@shop.example", "pattern noreply@*"),
    ("no-reply@bank.example", "pattern no-reply@*"),
])
def test_ignored(address, rule):
    assert RULES.match(address) == rule


@pytest.mark.parametrize("address", [
    "accounts.payable@shannonagri.ie", "ishitasinghal2021@gmail.com", "ap@notgithub.com",
    "noreply.team@customer.example", None, "",
])
def test_not_ignored(address):
    assert RULES.match(address) is None


def test_rule_is_in_the_database(db):
    assert load_ignore_list(db) == RULES  # inserted by migration 30122928abaa


def test_poll_does_not_store_ignored_senders(db, storage, fake_service):
    g = fake_service.gmail
    gid_sys = g.add_raw(_mail("GitHub <notifications@github.com>", "Run failed", attach=b"%PDF x"))
    gid_ok = g.add_raw(build_message(load_sample("R01-0007")).as_bytes())

    r = poll(db, service=fake_service, storage=storage)
    assert (r.ignored, r.stored) == (1, 1)
    assert db.scalars(select(EmailMessage).where(EmailMessage.gmail_id == gid_sys)).all() == []
    assert "AR-Ignored" in g.label_names(gid_sys) and "AR-Processed" not in g.label_names(gid_sys)
    a = db.scalar(select(AuditLog).where(AuditLog.action == "EMAIL_IGNORED", AuditLog.entity_id == gid_sys))
    assert a.details["sender"] == "notifications@github.com"
    assert a.details["reason"] == "ignored system sender" and a.details["date"].startswith("2026-10-27")
    # no files written for the ignored mail: only the R01-0007 e-mail folder exists
    assert [p.name for p in (storage.root / "emails").iterdir()] == [
        db.scalar(select(EmailMessage.email_ref).where(EmailMessage.gmail_id == gid_ok))]

    r2 = poll(db, service=fake_service, storage=storage)  # labelled -> not fetched again
    assert (r2.fetched, r2.ignored) == (0, 0)


def test_forwarded_from_ignored_sender_is_ignored(db, storage, fake_service):
    body = ("FYI\n\n---------- Forwarded message ---------\nFrom: GitHub <noreply@github.com>\n"
            "Subject: code\n\nYour code is 1234\n")
    fake_service.gmail.add_raw(_mail("colleague@acme.example", "Fwd: code", body))
    assert poll(db, service=fake_service, storage=storage).ignored == 1


def test_purge_lists_then_deletes_rows_and_files(db, storage, fake_service):
    g = fake_service.gmail
    raw_sys = _mail("Anthropic <invoice+statements@mail.anthropic.com>", "Your receipt", attach=b"%PDF r")
    gid_sys = g.add_raw(raw_sys)
    sys_mail = store_email(db, raw_sys, storage=storage, gmail_id=gid_sys)   # stored before the rule existed
    keep = store_email(db, build_message(load_sample("R01-0007")).as_bytes(), storage=storage, gmail_id="keep1")
    db.commit()
    sys_files = [sys_mail.raw_uri] + [a.storage_uri for a in
                                      db.scalars(select(EmailAttachment).where(EmailAttachment.email_id == sys_mail.id))]

    # only look at this test's e-mails (the laptop database may hold real ones too)
    found = [c for c in find_ignored_emails(db) if c.email.id in (sys_mail.id, keep.id)]
    assert [(c.email.email_ref, c.rule, c.attachments) for c in found] == [(sys_mail.email_ref, "domain anthropic.com", 1)]

    r = purge_emails(db, found, storage=storage, service=fake_service)
    assert r == {"emails_deleted": 1, "files_deleted": 2, "gmail_relabelled": 1}
    assert db.get(EmailMessage, sys_mail.id) is None and db.get(EmailMessage, keep.id) is not None
    assert db.scalars(select(EmailAttachment).where(EmailAttachment.email_id == sys_mail.id)).all() == []
    for uri in sys_files:
        with pytest.raises(FileNotFoundError):
            storage.get(uri)
    assert storage.get(keep.raw_uri)  # untouched
    assert not (storage.root / "emails" / sys_mail.email_ref).exists()  # empty folder removed
    assert g.label_names(gid_sys) >= {"AR-Ignored"} and "AR-Processed" not in g.label_names(gid_sys)
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "EMAIL_PURGED_IGNORED_SENDER",
                                             AuditLog.entity_id == sys_mail.email_ref))
    assert audit.details["reason"] == "ignored system sender" and audit.details["rule"] == "domain anthropic.com"
