"""Gmail poller against the laptop database (rolled back) with a fake Gmail mailbox."""
from email.message import EmailMessage as Mime

from sqlalchemy import select

from app.gmail.poller import poll
from app.gmail.sample_sender import build_message, load_sample
from app.models.ar import AuditLog, EmailAttachment, EmailMessage


def _emails(db, gmail_ids):
    return db.scalars(select(EmailMessage).where(EmailMessage.gmail_id.in_(gmail_ids))).all()


def _atts(db, email):
    return db.scalars(select(EmailAttachment).where(EmailAttachment.email_id == email.id)
                      .order_by(EmailAttachment.id)).all()


def test_poll_stores_sample_with_attachment_and_labels_it(db, storage, fake_service):
    g = fake_service.gmail
    raw = build_message(load_sample("R01-0007")).as_bytes()
    gid = g.add_raw(raw)

    r = poll(db, service=fake_service, storage=storage)
    assert (r.fetched, r.stored, r.failed) == (1, 1, 0)

    [e] = _emails(db, [gid])
    assert e.email_ref.startswith("EML-") and e.source == "sample" and e.sample_code == "R01-0007"
    assert e.sender_email == e.from_email == "accounts.payable@shannonagri.ie"
    assert e.sender_domain == "shannonagri.ie" and e.subject == "Remittance advice" and e.status == "NEW"
    assert e.body_text_clean.startswith("Dear Sir/Madam,")
    assert storage.get(e.raw_uri) == raw and len(e.sha256) == 64
    [a] = _atts(db, e)
    assert (a.filename, a.mime_type, a.depth, a.parent_id) == ("PaymentNotice_PAY441817.png", "image/png", 0, None)
    assert len(a.sha256) == 64 and a.size_bytes == len(storage.get(a.storage_uri))
    assert "AR-Processed" in g.label_names(gid)
    assert db.scalar(select(AuditLog).where(AuditLog.entity_id == e.email_ref)).action == "EMAIL_INGESTED"


def test_second_poll_creates_no_duplicates(db, storage, fake_service):
    g = fake_service.gmail
    gid = g.add_raw(build_message(load_sample("R01-0007")).as_bytes())
    poll(db, service=fake_service, storage=storage)
    r2 = poll(db, service=fake_service, storage=storage)
    assert (r2.fetched, r2.stored) == (0, 0)
    assert len(_emails(db, [gid])) == 1


def test_label_failure_is_healed_without_duplicate(db, storage, fake_service):
    g = fake_service.gmail
    gid = g.add_raw(build_message(load_sample("R01-0007")).as_bytes())
    g.fail_modify_once = True                      # stored in DB, but labelling fails
    r1 = poll(db, service=fake_service, storage=storage)
    assert r1.failed == 1 and len(_emails(db, [gid])) == 1
    assert "AR-Processed" not in g.label_names(gid)
    r2 = poll(db, service=fake_service, storage=storage)  # next poll sees it again ...
    assert (r2.already_stored, r2.stored) == (1, 0)       # ... and only labels it
    assert "AR-Processed" in g.label_names(gid) and len(_emails(db, [gid])) == 1


def test_zip_sample_stores_inner_files(db, storage, fake_service):
    gid = fake_service.gmail.add_raw(build_message(load_sample("R30-0165")).as_bytes())
    poll(db, service=fake_service, storage=storage)
    [e] = _emails(db, [gid])
    atts = _atts(db, e)
    [zip_row] = [a for a in atts if a.filename.endswith(".zip")]
    children = [a for a in atts if a.parent_id == zip_row.id]
    assert zip_row.depth == 0 and children and all(c.depth == 1 for c in children)
    assert e.error is None


def test_outbound_and_forwarded(db, storage, fake_service):
    g = fake_service.gmail
    out = Mime()
    out["From"], out["Subject"], out["X-AR-Demo"] = "processintelligence1@gmail.com", "[AR-DEMO] reminder", "outbound"
    out.set_content("our own outbound mail")
    gid_out = g.add_raw(out.as_bytes())
    gid_fwd = g.add_raw(build_message(load_sample("R24-0139")).as_bytes())

    r = poll(db, service=fake_service, storage=storage)
    assert (r.skipped_outbound, r.stored) == (1, 1)
    assert "AR-Outbound" in g.label_names(gid_out) and _emails(db, [gid_out]) == []
    [f] = _emails(db, [gid_fwd])
    assert f.is_forwarded and f.sender_email == "tesoreria@iberiacomponentes.es"
    assert "adjuntamos el aviso de pago" in f.body_text_clean
