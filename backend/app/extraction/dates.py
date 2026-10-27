"""Dates in EN / DE / FR / ES / PT / JA, including Japanese eras and relative promise dates.

Fixed:     2026-10-28  2026/11/02  2026.10.19  28.10.2026  28/10/2026  10/28/2026 (US)  16-Nov-2026
           18 Nov 2026  Nov 18, 2026  November 02, 2026  23. Oktober 2026  25 octobre 2026
           27 de noviembre de 2026  25 de novembro de 2026  2026年11月27日  令和8年11月27日  11月25日
Relative:  next Friday, end of (next) month, within 7 days, in 10 days, tomorrow, next week (+ DE/FR/ES/PT/JA)
           -> resolved against the e-mail date; the original wording is kept (raw) as evidence.
Ambiguous day/month (03/11/2026): day first, unless the sender looks American (prefer_us) - and the
result says it was ambiguous. A reading that is not a valid date is dropped.
"""
import calendar
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.classification.signals import fold

MONTHS = {
    # English
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4, "may": 5,
    "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
    # German (folded: maerz)
    "januar": 1, "jaenner": 1, "februar": 2, "maerz": 3, "mai": 5, "juni": 6, "juli": 7, "oktober": 10,
    "okt": 10, "dezember": 12, "dez": 12,
    # French (folded: fevrier, aout, decembre)
    "janvier": 1, "fevrier": 2, "fevr": 2, "mars": 3, "avril": 4, "avr": 4, "juin": 6, "juillet": 7,
    "juil": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
    # Spanish
    "enero": 1, "ene": 1, "febrero": 2, "marzo": 3, "abril": 4, "abr": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "ago": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12, "dic": 12,
    # Portuguese (folded: marco)
    "janeiro": 1, "fevereiro": 2, "marco": 3, "maio": 5, "junho": 6, "julho": 7, "setembro": 9, "set": 9,
    "outubro": 10, "out": 10, "novembro": 11, "dezembro": 12,
}
_MON = "|".join(sorted(MONTHS, key=len, reverse=True))
WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
    "montag": 0, "dienstag": 1, "mittwoch": 2, "donnerstag": 3, "freitag": 4, "samstag": 5, "sonntag": 6,
    "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4, "samedi": 5, "dimanche": 6,
    "lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6,
    "segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4,
}
_WD = "|".join(sorted(WEEKDAYS, key=len, reverse=True))
ERAS = {"令和": 2018, "平成": 1988, "昭和": 1925}  # era year 1 = base + 1


@dataclass
class FoundDate:
    value: date
    raw: str                      # as written (evidence)
    start: int
    end: int
    kind: str                     # iso | numeric | named | japanese | relative
    ambiguous: bool = False       # day/month order was a guess
    readings: list[date] = field(default_factory=list)


def _safe(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _num(s: str) -> int:
    return 1 if s == "元" else int(s)


# (pattern, kind) on folded text - order matters (longer forms first); spans never overlap
_FIXED = [
    (re.compile(r"(令和|平成|昭和)\s*(\d{1,2}|元)\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"), "era"),
    (re.compile(r"(20\d\d)\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"), "jp_ymd"),
    (re.compile(r"(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*日"), "jp_md"),
    (re.compile(r"(?<![\d.])(20\d\d)[-/.](\d{1,2})[-/.](\d{1,2})(?!\d|\.\d)"), "ymd"),
    (re.compile(rf"(?<!\d)(\d{{1,2}})(?:st|nd|rd|th|er)?\.?[\s-]+(?:de\s+)?({_MON})\.?,?[\s-]+(?:de\s+)?(20\d\d)(?!\d)"), "d_mon_y"),
    (re.compile(rf"\b({_MON})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(20\d\d)(?!\d)"), "mon_d_y"),
    (re.compile(r"(?<![\d.])(\d{1,2})([./-])(\d{1,2})\2(20\d\d|\d\d)(?!\d|\.\d)"), "dmy"),
]


def find_dates(text: str, base: date | None = None, prefer_us: bool = False) -> list[FoundDate]:
    """Every fixed and relative date in a text, in text order. `base` = e-mail date (relative dates,
    Japanese dates without a year). Positions refer to the folded text (same as the input unless it
    contains German umlauts)."""
    t = fold(text)
    src = text if len(t) == len(text) else t  # umlauts make the folded text longer: then quote the folded text
    found: list[FoundDate] = []
    taken: list[tuple[int, int]] = []

    def free(a: int, b: int) -> bool:
        return all(b <= s or a >= e for s, e in taken)

    for rx, kind in _FIXED:
        for m in rx.finditer(t):
            if not free(m.start(), m.end()):
                continue
            g = m.groups()
            readings: list[date | None]
            if kind == "era":
                readings = [_safe(ERAS[g[0]] + _num(g[1]), int(g[2]), int(g[3]))]
            elif kind == "jp_ymd":
                readings = [_safe(int(g[0]), int(g[1]), int(g[2]))]
            elif kind == "jp_md":
                if base is None:
                    continue
                d = _safe(base.year, int(g[0]), int(g[1]))
                if d and d < base - timedelta(days=60):  # "11月25日" written in December means next year
                    d = _safe(base.year + 1, int(g[0]), int(g[1]))
                readings = [d]
            elif kind == "ymd":
                readings = [_safe(int(g[0]), int(g[1]), int(g[2]))]
            elif kind == "d_mon_y":
                readings = [_safe(int(g[2]), MONTHS[g[1]], int(g[0]))]
            elif kind == "mon_d_y":
                readings = [_safe(int(g[2]), MONTHS[g[0]], int(g[1]))]
            else:  # dmy: dd/mm/yyyy or (US) mm/dd/yyyy
                y = int(g[3]) + (2000 if len(g[3]) == 2 else 0)
                a, b = int(g[0]), int(g[2])
                day_first, month_first = _safe(y, b, a), _safe(y, a, b)
                readings = [month_first, day_first] if prefer_us else [day_first, month_first]
            readings = [r for r in readings if r]
            if not readings:
                continue
            uniq = sorted(set(readings))
            found.append(FoundDate(readings[0], src[m.start():m.end()], m.start(), m.end(),
                                   "japanese" if kind.startswith(("era", "jp")) else kind,
                                   ambiguous=len(uniq) > 1, readings=uniq))
            taken.append((m.start(), m.end()))
    if base is not None:
        for r in find_relative(t, base):
            if free(r.start, r.end):
                r.raw = src[r.start:r.end]
                found.append(r)
    return sorted(found, key=lambda f: f.start)


# --------------------------------------------------------------------------- relative dates
def _end_of_month(d: date, months_ahead: int = 0) -> date:
    y, m = d.year + (d.month - 1 + months_ahead) // 12, (d.month - 1 + months_ahead) % 12 + 1
    return date(y, m, calendar.monthrange(y, m)[1])


def _next_weekday(base: date, wd: int) -> date:
    """The coming weekday after `base` ("next Friday" written on a Monday = that week's Friday)."""
    return base + timedelta(days=(wd - base.weekday()) % 7 or 7)


_N = r"(\d{1,3})"
_RELATIVE = [
    # within / in N days  (EN, DE, FR, ES, PT, JA)
    (re.compile(rf"\b(?:within|in)\s+{_N}\s+(?:business\s+|working\s+)?days?\b|\b{_N}\s+days\s+from\s+(?:today|now)\b"), "days"),
    (re.compile(rf"\b(?:innerhalb\s+von|in)\s+{_N}\s+(?:werk|arbeits)?tagen\b"), "days"),
    (re.compile(rf"\b(?:sous|dans|d'ici)\s+{_N}\s+jours\b"), "days"),
    (re.compile(rf"\b(?:dentro\s+de|en)\s+{_N}\s+dias\b"), "days"),
    (re.compile(rf"\b(?:dentro\s+de|em)\s+{_N}\s+dias\b"), "days"),
    (re.compile(rf"{_N}\s*日以内"), "days"),
    # end of (next) month
    (re.compile(r"\bend\s+of\s+(?:the\s+)?next\s+month\b|\bende\s+(?:des\s+)?naechsten\s+monats\b|\bfin\s+du\s+mois\s+prochain\b|"
                r"\bfin(?:al)?\s+del?\s+(?:mes|mês)\s+(?:que\s+viene|proximo)\b|\bfi(?:m|nal)\s+do\s+proximo\s+mes\b|来月末"), "eom_next"),
    (re.compile(r"\bend\s+of\s+(?:the\s+|this\s+)?month\b|\bmonth[-\s]end\b|\bmonatsende\b|\bende\s+(?:des|dieses)\s+monats\b|"
                r"\bfin\s+(?:du|de)\s+mois\b|\bfin(?:al)?\s+de(?:l)?\s+mes\b|\bfi(?:m|nal)\s+do\s+mes\b|月末"), "eom"),
    # next week / tomorrow
    (re.compile(r"\bnext\s+week\b|\bnaechste[n]?\s+woche\b|\bla\s+semaine\s+prochaine\b|\bla\s+proxima\s+semana\b|"
                r"\bsemana\s+que\s+vem\b|\bproxima\s+semana\b|来週"), "next_week"),
    (re.compile(r"\btomorrow\b|\bmorgen\b|\bdemain\b|\bmanana\b|\bamanha\b|明日"), "tomorrow"),
    # (next / this / coming) weekday
    (re.compile(rf"\b(?:next|this|coming|naechsten|kommenden|el\s+proximo|la\s+proxima|proxima|proximo)\s+({_WD})(?:-feira)?\b|"
                rf"\b({_WD})(?:-feira)?\s+(?:prochain|que\s+vem|next\s+week)\b|\bon\s+({_WD})\b"), "weekday"),
]


def find_relative(folded: str, base: date) -> list[FoundDate]:
    out: list[FoundDate] = []
    for rx, kind in _RELATIVE:
        for m in rx.finditer(folded):
            if any(not (m.end() <= f.start or m.start() >= f.end) for f in out):
                continue
            if kind == "days":
                n = int(next(g for g in m.groups() if g))
                value = base + timedelta(days=n)
            elif kind == "eom":
                value = _end_of_month(base)
            elif kind == "eom_next":
                value = _end_of_month(base, 1)
            elif kind == "next_week":
                value = base + timedelta(days=7 - base.weekday())  # Monday of next week
            elif kind == "tomorrow":
                value = base + timedelta(days=1)
            else:
                wd = WEEKDAYS[next(g for g in m.groups() if g)]
                value = _next_weekday(base, wd)
            out.append(FoundDate(value, m.group(0), m.start(), m.end(), "relative", readings=[value]))
    return out


def parse_date(text: str, base: date | None = None, prefer_us: bool = False) -> FoundDate | None:
    """The first date in a short text (e.g. a table cell or a "Payment date: ..." value)."""
    found = find_dates(text, base, prefer_us)
    return found[0] if found else None
