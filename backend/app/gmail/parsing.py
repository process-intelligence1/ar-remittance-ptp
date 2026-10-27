"""Turn a raw RFC 822 e-mail into the fields we store. Pure functions - no Gmail, no database.

- parse_raw_email()   headers, body text, attachments (incl. inline parts)
- detect_forward()    manual forwards: original sender taken from the forwarded header block
- clean_body()        body without quoted reply history
- unpack_zip()        files inside a ZIP (recursively), with size/count/depth limits
"""
import io
import mimetypes
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from html import unescape

from mailparser_reply import EmailReplyParser

from app.storage import safe_filename

# Languages of the sample e-mails supported by mail-parser-reply (it has no Portuguese rules).
REPLY_LANGUAGES = ["en", "de", "fr", "es", "it", "nl", "ja", "zh"]

# Lines that start a manually forwarded message (Gmail, Outlook, Apple Mail; EN/DE/FR/ES/PT/JA).
FORWARD_MARKERS = re.compile(
    r"^[ \t>]*(?:"
    r"-{3,}\s*(?:Forwarded message|Weitergeleitete Nachricht|Message transf[ée]r[ée]|Mensaje reenviado"
    r"|Mensagem encaminhada|Original Message|Urspr[üu]ngliche Nachricht|Message d'origine"
    r"|Mensaje original|Mensagem original)\s*-{3,}"
    r"|Begin forwarded message:"
    r"|-{3,}\s*転送されたメッセージ\s*-{3,}"
    r")[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
# Header labels inside the forwarded block
_FWD_FROM = re.compile(r"^[ \t>]*(?:From|Von|De|Desde|差出人|送信者)\s*[:：]\s*(.+)$", re.IGNORECASE | re.MULTILINE)
_FWD_HEADER_LINE = re.compile(
    r"^[ \t>]*(?:From|Von|De|Desde|差出人|送信者|Date|Datum|Fecha|Data|Envoyé|Enviado|Sent|日付|送信日時"
    r"|Subject|Betreff|Objet|Asunto|Assunto|件名|To|An|À|Para|宛先|Cc)\s*[:：]",
    re.IGNORECASE,
)

ZIP_MAX_DEPTH = 3
ZIP_MAX_FILES = 200
ZIP_MAX_TOTAL_BYTES = 50 * 1024 * 1024


@dataclass
class ParsedAttachment:
    filename: str
    mime_type: str
    data: bytes
    is_inline: bool = False


@dataclass
class ParsedEmail:
    rfc_message_id: str | None
    subject: str | None
    from_name: str | None
    from_email: str | None
    date: datetime | None
    body_text: str
    headers: dict[str, str]
    attachments: list[ParsedAttachment] = field(default_factory=list)
    body_html: str | None = None  # HTML part, if any (its tables are read in M02)


@dataclass
class ForwardInfo:
    is_forwarded: bool
    sender_name: str | None = None
    sender_email: str | None = None
    note: str = ""            # what the forwarder wrote above the forwarded block
    forwarded_body: str = ""  # the original message body (without its header lines)


@dataclass
class ZipEntry:
    filename: str
    mime_type: str
    data: bytes
    depth: int
    children: list["ZipEntry"] = field(default_factory=list)


# --------------------------------------------------------------------------- headers / addresses
def split_address(value: str | None) -> tuple[str | None, str | None]:
    """'Name <a@b.com>' -> ('Name', 'a@b.com'); lower-cases the address."""
    if not value:
        return None, None
    pairs = [(n, a) for n, a in getaddresses([value]) if a and "@" in a]
    if not pairs:
        return None, None
    name, addr = pairs[0]
    return (name.strip().strip('"') or None), addr.strip().lower()


def domain_of(email_address: str | None) -> str | None:
    if not email_address or "@" not in email_address:
        return None
    return email_address.rsplit("@", 1)[1].lower()


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        d = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------- body + attachments
def html_to_text(html: str) -> str:
    """Readable text from HTML. Table cells are separated by a tab and each row is one line, so
    "invoice <td> amount" stays together and the columns can be found again (M02)."""
    html = re.sub(r"(?is)<(script|style|head).*?</\1>", "", html)
    html = re.sub(r"(?i)</t[dh]\s*>", "\t", html)
    html = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>|</h\d>|</table>", "\n", html)
    html = re.sub(r"(?s)<[^>]+>", "", html)
    text = unescape(html)
    text = re.sub(r"[ \xa0]+", " ", text)
    text = re.sub(r" *\t[ \t]*", "\t", text)
    text = "\n".join(line.strip(" ").rstrip("\t") for line in text.split("\n"))
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()


def _part_text(part: EmailMessage) -> str:
    try:
        return part.get_content()
    except (LookupError, UnicodeDecodeError):
        payload = part.get_payload(decode=True) or b""
        return payload.decode("utf-8", errors="replace")


def parse_raw_email(raw: bytes) -> ParsedEmail:
    msg: EmailMessage = BytesParser(policy=policy.default).parsebytes(raw)
    from_name, from_email = split_address(msg.get("From"))

    plain, html = [], []
    attachments: list[ParsedAttachment] = []
    for part in msg.walk():
        if part.is_multipart():
            continue
        ctype = part.get_content_type()
        disposition = part.get_content_disposition()  # None | inline | attachment
        filename = part.get_filename()
        if filename or disposition == "attachment":
            data = part.get_payload(decode=True) or b""
            name = safe_filename(filename or "", default=f"attachment{mimetypes.guess_extension(ctype) or ''}")
            attachments.append(ParsedAttachment(name, ctype, data, is_inline=disposition == "inline"))
        elif ctype == "text/plain":
            plain.append(_part_text(part))
        elif ctype == "text/html":
            html.append(_part_text(part))
        elif disposition == "inline" or ctype.startswith("image/"):
            data = part.get_payload(decode=True) or b""
            ext = mimetypes.guess_extension(ctype) or ""
            attachments.append(ParsedAttachment(f"inline{len(attachments) + 1}{ext}", ctype, data, is_inline=True))

    body = "\n".join(plain).strip() if plain else html_to_text("\n".join(html))
    headers = {k.lower(): str(v) for k, v in msg.items()}
    return ParsedEmail(
        rfc_message_id=(msg.get("Message-ID") or "").strip() or None,
        subject=str(msg.get("Subject")) if msg.get("Subject") else None,
        from_name=from_name,
        from_email=from_email,
        date=_parse_date(msg.get("Date")),
        body_text=body.replace("\r\n", "\n"),
        headers=headers,
        attachments=attachments,
        body_html="\n".join(html) or None,
    )


# --------------------------------------------------------------------------- forwards / replies
def detect_forward(body: str) -> ForwardInfo:
    m = FORWARD_MARKERS.search(body or "")
    if not m:
        return ForwardInfo(is_forwarded=False)
    note, block = body[: m.start()].strip(), body[m.end():]

    # Header lines of the forwarded message, up to the first non-header line after them
    lines = block.lstrip("\n").split("\n")
    i = 0
    while i < len(lines) and (_FWD_HEADER_LINE.match(lines[i]) or (i == 0 and not lines[i].strip())):
        i += 1
    header_text = "\n".join(lines[:i])
    forwarded_body = "\n".join(lines[i:]).strip()

    name = addr = None
    fm = _FWD_FROM.search(header_text)
    if fm:
        raw = fm.group(1).strip()
        # Outlook writes "Name [mailto:a@b.com]"
        raw = re.sub(r"\[mailto:([^\]]+)\]", r"<\1>", raw)
        name, addr = split_address(raw)
    return ForwardInfo(True, name, addr, note, forwarded_body)


def strip_replies(text: str) -> str:
    """Latest reply only, without quoted history ('On ... wrote:', '> ...', Outlook headers)."""
    if not text or not text.strip():
        return ""
    try:
        parsed = EmailReplyParser(languages=REPLY_LANGUAGES).read(text)
        latest = parsed.replies[0].body if parsed.replies else text
    except Exception:  # the parser is heuristic; never lose the body because of it
        latest = text
    return (latest or text).strip()


def clean_body(body: str, fwd: ForwardInfo | None = None) -> str:
    """body_text_clean: quoted history removed. For a forward, keep the forwarder's note and the
    forwarded message itself (that is the content we need), each without older quoted replies."""
    fwd = fwd or detect_forward(body)
    if not fwd.is_forwarded:
        return strip_replies(body)
    parts = [strip_replies(fwd.note), strip_replies(fwd.forwarded_body)]
    return "\n\n".join(p for p in parts if p)


# --------------------------------------------------------------------------- ZIP files
def guess_mime(filename: str) -> str:
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"


def is_zip(filename: str, data: bytes) -> bool:
    # .docx/.xlsx are ZIP containers too, but they are documents, not archives to unpack
    office = filename.lower().endswith((".docx", ".xlsx", ".pptx", ".odt", ".ods"))
    return filename.lower().endswith(".zip") or (data[:4] == b"PK\x03\x04" and not office)


def unpack_zip(data: bytes, depth: int = 1, _budget: list[int] | None = None) -> list[ZipEntry]:
    """Files inside a ZIP; nested ZIPs are unpacked into `children`. Raises ValueError if the
    archive breaks the safety limits (too deep, too many files, too large when unpacked)."""
    if depth > ZIP_MAX_DEPTH:
        raise ValueError(f"ZIP nested deeper than {ZIP_MAX_DEPTH} levels")
    budget = _budget if _budget is not None else [ZIP_MAX_FILES, ZIP_MAX_TOTAL_BYTES]
    entries: list[ZipEntry] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            if info.is_dir() or info.filename.startswith("__MACOSX/") or info.filename.split("/")[-1].startswith("._"):
                continue
            budget[0] -= 1
            budget[1] -= info.file_size
            if budget[0] < 0 or budget[1] < 0:
                raise ValueError("ZIP exceeds the file-count or size limit")
            content = zf.read(info)
            name = safe_filename(_zip_name(info))
            entry = ZipEntry(name, guess_mime(name), content, depth)
            if is_zip(name, content):
                entry.children = unpack_zip(content, depth + 1, budget)
            entries.append(entry)
    return entries


def _zip_name(info: zipfile.ZipInfo) -> str:
    # ZIPs made on Windows without the UTF-8 flag store names in cp437; try to recover UTF-8 names
    if info.flag_bits & 0x800:
        return info.filename
    try:
        return info.filename.encode("cp437").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename
