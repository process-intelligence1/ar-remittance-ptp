"""Raw e-mail parsing, forward detection, reply stripping, ZIP unpacking, storage helpers."""
import io
import zipfile
from email.message import EmailMessage

import pytest

from app.gmail import parsing
from app.storage import LocalStorage, safe_filename


def _zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _raw(body: str, frm="Accounts <AP@Example.COM>", attachments=()) -> bytes:
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = frm, "processintelligence1@gmail.com", "Payment advice"
    m["Date"] = "Fri, 23 Oct 2026 19:58:56 +0000"
    m["Message-ID"] = "<abc@example.com>"
    m.set_content(body)
    for name, ctype, data in attachments:
        maintype, subtype = ctype.split("/")
        m.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    return m.as_bytes()


def test_parse_headers_body_and_attachments():
    p = parsing.parse_raw_email(_raw("Kindly note our payment.", attachments=[("advice.pdf", "application/pdf", b"%PDF-1.7 x")]))
    assert p.from_email == "ap@example.com" and p.from_name == "Accounts"
    assert p.subject == "Payment advice" and p.rfc_message_id == "<abc@example.com>"
    assert p.date.isoformat() == "2026-10-23T19:58:56+00:00"
    assert p.body_text.strip() == "Kindly note our payment."
    assert [(a.filename, a.mime_type, a.data) for a in p.attachments] == [("advice.pdf", "application/pdf", b"%PDF-1.7 x")]


def test_html_only_body_becomes_text():
    m = EmailMessage()
    m["From"] = "a@b.com"
    m.add_alternative("<html><body><p>Paid invoice <b>4711</b></p><p>Thanks</p></body></html>", subtype="html")
    p = parsing.parse_raw_email(m.as_bytes())
    assert "Paid invoice 4711" in p.body_text and "Thanks" in p.body_text and "<" not in p.body_text


def test_forwarded_gmail_style_takes_original_sender():
    body = ("Resending for your records.\n\n---------- Forwarded message ---------\n"
            "From: Tesoreria <tesoreria@iberiacomponentes.es>\nDate: Mon, 26 Oct 2026 13:54:18 -0000\n"
            "Subject: Pago factura FA2026-09035\nTo: ar.demo.inbox@gmail.com\n\n"
            "Estimados senores:\n\nadjuntamos el aviso de pago.\n")
    f = parsing.detect_forward(body)
    assert f.is_forwarded and f.sender_email == "tesoreria@iberiacomponentes.es" and f.sender_name == "Tesoreria"
    assert f.note == "Resending for your records."
    assert f.forwarded_body.startswith("Estimados senores:")
    clean = parsing.clean_body(body, f)
    assert "Resending for your records." in clean and "adjuntamos el aviso de pago." in clean
    assert "Forwarded message" not in clean


@pytest.mark.parametrize("marker,label", [
    ("-----Original Message-----", "From"),
    ("-------- Weitergeleitete Nachricht --------", "Von"),
    ("-------- Message transféré --------", "De"),
    ("Begin forwarded message:", "From"),
])
def test_forward_markers_in_several_styles(marker, label):
    body = f"FYI\n\n{marker}\n{label}: Max Muster [mailto:max@kunde.de]\nSubject: Zahlung\n\nText"
    f = parsing.detect_forward(body)
    assert f.is_forwarded and f.sender_email == "max@kunde.de"


def test_not_forwarded():
    assert parsing.detect_forward("Please find attached our remittance.").is_forwarded is False


def test_reply_history_removed():
    body = ("We will pay invoice 90001234 on 5 Nov.\n\nOn Mon, 19 Oct 2026 at 10:15, AR Team "
            "<ar@acme.com> wrote:\n> Dear customer, invoice 90001234 is overdue.\n> Regards\n")
    assert parsing.clean_body(body) == "We will pay invoice 90001234 on 5 Nov."


def test_domain_and_split_address():
    assert parsing.split_address('"Shannon Agri" <Accounts.Payable@ShannonAgri.ie>') == ("Shannon Agri", "accounts.payable@shannonagri.ie")
    assert parsing.split_address("not an address") == (None, None)
    assert parsing.domain_of("a@B.Example.com") == "b.example.com" and parsing.domain_of(None) is None


def test_unpack_nested_zip():
    inner = _zip({"page2.pdf": b"%PDF inner"})
    outer = _zip({"advice.pdf": b"%PDF outer", "docs/": b"", "more.zip": inner, "__MACOSX/._advice.pdf": b"junk"})
    entries = parsing.unpack_zip(outer)
    names = [e.filename for e in entries]
    assert names == ["advice.pdf", "more.zip"]
    assert entries[0].depth == 1 and entries[0].mime_type == "application/pdf"
    assert [(c.filename, c.depth, c.data) for c in entries[1].children] == [("page2.pdf", 2, b"%PDF inner")]


def test_zip_limits(monkeypatch):
    monkeypatch.setattr(parsing, "ZIP_MAX_FILES", 2)
    with pytest.raises(ValueError):
        parsing.unpack_zip(_zip({"a.txt": b"1", "b.txt": b"2", "c.txt": b"3"}))
    nested = _zip({"x.txt": b"x"})
    for _ in range(parsing.ZIP_MAX_DEPTH):
        nested = _zip({"n.zip": nested})
    monkeypatch.setattr(parsing, "ZIP_MAX_FILES", 200)
    with pytest.raises(ValueError):
        parsing.unpack_zip(nested)


def test_office_files_are_not_unpacked():
    docx_like = _zip({"word/document.xml": b"<w/>"})
    assert parsing.is_zip("advice.docx", docx_like) is False
    assert parsing.is_zip("advice.zip", docx_like) is True
    assert parsing.is_zip("noext", docx_like) is True


def test_safe_filename_and_local_storage(tmp_path):
    assert safe_filename("..\\..\\evil:name?.pdf") == "evil_name_.pdf"
    assert safe_filename("") == "file"
    st = LocalStorage(tmp_path)
    uri = st.put("../../emails/EML-1/a.txt", b"hello")
    assert uri == "local:emails/EML-1/a.txt" and (tmp_path / "emails/EML-1/a.txt").exists()
    assert st.get(uri) == b"hello"
    with pytest.raises(ValueError):
        st.get("blob:emails/EML-1/a.txt")
