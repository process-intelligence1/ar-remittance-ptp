"""Tables written as text: column-aligned plain text (bodies, OCR output) and HTML <table>s.

Plain text example (sample R22-0128):
    Invoice No.            Amount paid
      Inv# UK-1043514      GBP 1,707.60
      UK-1043671           GBP 1,673.51
Columns are separated by 2+ spaces or a tab. The header line fixes the column positions; each
following line is cut into cells by those positions, so an empty cell stays empty.
"""
import re
from html.parser import HTMLParser

_SEGMENT = re.compile(r"\S+(?: \S+)*")  # runs of text separated by single spaces


def _segments(line: str) -> list[tuple[int, str]]:
    line = line.replace("\t", "    ")
    return [(m.start(), m.group()) for m in _SEGMENT.finditer(line)]


def _pipe_cells(line: str) -> list[str] | None:
    s = line.strip()
    if s.count("|") >= 2 and not set(s) <= set("|-+: "):
        return [c.strip() for c in s.strip("|").split("|")]
    return None


def find_text_tables(text: str, min_rows: int = 1) -> list[dict]:
    """Tables in plain text. Returns [{"rows": [[...], ...], "first_line": n}] (header = first row)."""
    lines = (text or "").replace("\r\n", "\n").split("\n")
    tables: list[dict] = []
    i = 0
    while i < len(lines):
        # --- pipe tables: | a | b |   (separator lines like |---|---| are skipped)
        if _pipe_cells(lines[i]):
            start, rows = i, []
            while i < len(lines) and lines[i].strip() and (
                    _pipe_cells(lines[i]) or set(lines[i].strip()) <= set("|-+: ")):
                cells = _pipe_cells(lines[i])
                if cells:
                    rows.append(cells)
                i += 1
            if len(rows) >= 1 + min_rows:
                tables.append({"rows": rows, "first_line": start})
            continue
        # --- aligned columns: header with 2+ segments separated by 2+ spaces, rows until a blank line
        head = _segments(lines[i])
        if len(head) >= 2 and _gap_ok(lines[i]) and not lines[i].rstrip().endswith(":"):
            cols = [pos for pos, _ in head]
            rows, j = [[seg for _, seg in head]], i + 1
            head_is_label = _is_label(head[0][1])
            while j < len(lines) and lines[j].strip():
                segs = _segments(lines[j])
                if len(segs) > len(cols) + 1:  # clearly a different block of text
                    break
                if _is_label(segs[0][1]) != head_is_label:
                    break  # "Label: value" lines and a column table are separate tables
                row = [""] * len(cols)
                for pos, seg in segs:
                    k = max((n for n, c in enumerate(cols) if c <= pos + 3), default=0)
                    row[k] = (row[k] + " " + seg).strip()
                rows.append(row)
                j += 1
            if len(rows) >= 1 + min_rows and _looks_tabular(rows):
                tables.append({"rows": rows, "first_line": i})
                i = j
                continue
        i += 1
    return tables


_KEY_VALUE = re.compile(r"^[^\d:：]{2,40}[:：]\s*\S")  # "Zahlungsdatum: 19.10.2026"


def _is_label(cell: str) -> bool:
    """A 'Label:' cell, or a whole 'Label: value' line."""
    cell = cell.strip()
    return cell.endswith((":", "：")) or bool(_KEY_VALUE.match(cell))


def _gap_ok(line: str) -> bool:
    return bool(re.search(r"\S(?: {2,}|\t)\S", line))


def _looks_tabular(rows: list[list[str]]) -> bool:
    """At least one data row with a value outside the first column, and not just prose."""
    data = rows[1:]
    if not data:
        return False
    filled = sum(1 for r in data for c in r[1:] if c)
    wordy = sum(1 for r in rows for c in r if len(c.split()) > 8)
    # a 2+ column header over a single row with only its first cell (R02: amount left empty) counts too
    single_keyed_row = len(rows[0]) >= 2 and len(data) == 1 and bool(data[0][0])
    return (filled >= 1 or len(data) >= 2 or single_keyed_row) and wordy == 0


class _HtmlTables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._stack: list[list[list[str]]] = []
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._stack.append([])
        elif tag == "tr" and self._stack:
            self._stack[-1].append([])
        elif tag in ("td", "th") and self._stack:
            if not self._stack[-1]:
                self._stack[-1].append([])
            self._cell = []
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._stack and self._cell is not None:
            self._stack[-1][-1].append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "table" and self._stack:
            rows = [r for r in self._stack.pop() if any(c for c in r)]
            if rows:
                self.tables.append(rows)

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def find_html_tables(html: str) -> list[list[list[str]]]:
    p = _HtmlTables()
    try:
        p.feed(html or "")
        p.close()
    except Exception:  # broken HTML: keep what was found
        pass
    return p.tables
