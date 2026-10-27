"""Sample sender: building RFC 822 messages from data/samples/emails/<CODE>/."""
from pathlib import Path

import pytest

from app.gmail import parsing
from app.gmail.sample_sender import build_message, import_to_inbox, load_sample, samples_root

ALL_CODES = sorted(p.name for p in samples_root().iterdir() if (p / "body.txt").exists())


def test_load_r01_0007():
    s = load_sample("R01-0007")
    assert s.headers["from"] == "accounts.payable@shannonagri.ie"
    assert s.headers["subject"] == "Remittance advice"
    assert [p.name for p in s.attachments] == ["PaymentNotice_PAY441817.png"]
    assert s.body.startswith("Dear Sir/Madam,")


def test_message_keeps_customer_as_sender_and_tags_sample():
    msg = build_message(load_sample("R01-0007"))
    p = parsing.parse_raw_email(msg.as_bytes())
    assert p.from_email == "accounts.payable@shannonagri.ie"
    assert p.headers["x-ar-sample"] == "R01-0007"
    assert p.headers["to"] == "processintelligence1@gmail.com"
    # live send: dated now; the sample's own date (no zone in body.txt -> UTC) kept in X-Original-Date
    assert p.headers["x-original-date"] == "Fri, 23 Oct 2026 19:58:56 +0000"
    png = (samples_root() / "R01-0007" / "PaymentNotice_PAY441817.png").read_bytes()
    assert [(a.filename, a.mime_type) for a in p.attachments] == [("PaymentNotice_PAY441817.png", "image/png")]
    assert p.attachments[0].data == png


def test_unknown_sample():
    with pytest.raises(FileNotFoundError):
        load_sample("X99-9999")


@pytest.mark.parametrize("code", ALL_CODES)
def test_every_sample_builds_and_round_trips(code):
    sample = load_sample(code)
    p = parsing.parse_raw_email(build_message(sample).as_bytes())
    assert p.from_email and "@" in p.from_email
    assert sorted(a.filename for a in p.attachments) == sorted(x.name for x in sample.attachments)


def test_import_uses_inbox_unread_and_date_header(fake_service):
    r = import_to_inbox(fake_service, build_message(load_sample("R30-0165")))
    g = fake_service.gmail
    assert g.messages[r["id"]]["labelIds"] == ["INBOX", "UNREAD"]
    assert g.last_import_kwargs["internalDateSource"] == "dateHeader"


def test_sample_count():
    assert len(ALL_CODES) == 234
