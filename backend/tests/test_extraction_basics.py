"""M04 building blocks: invoice-number normalisation and shapes, amounts, dates (incl. relative / Japanese)."""
from datetime import date
from decimal import Decimal

import pytest

from app.extraction.amounts import find_amounts, parse_number
from app.extraction.dates import find_dates, parse_date
from app.extraction.refs import clean_ref, find_refs, normalise_ref, valid_iban

BASE = date(2026, 10, 28)  # a Wednesday


# --------------------------------------------------------------------------- references
@pytest.mark.parametrize("raw, norm", [
    ("MUM/2627/04212", "MUM262704212"), ("uk-1043617", "UK1043617"), ("JP-26-002330", "JP26002330"),
    ("0090031223", "90031223"), ("FA2026-09168", "FA202609168"), ("SRV 100354", "SRV100354"), ("90.031.237", "90031237"),
])
def test_normalise_ref_same_rule_as_matching(raw, norm):
    assert normalise_ref(raw) == norm


@pytest.mark.parametrize("raw, clean", [("Inv# UK-1043514", "UK-1043514"), ("INV-91004752", "91004752"),
                                        ("Invoice No. 90031280", "90031280"), ("No. MUM/2627/05208", "MUM/2627/05208")])
def test_clean_ref_drops_written_labels(raw, clean):
    assert clean_ref(raw) == clean


def test_find_refs_all_bsid_shapes_but_not_payment_refs_or_dates():
    text = ("90031237 91005413 MUM/2627/04212 UK-1043617 CN-1031273 JP-26-002330 FA2026-09168 SRV-100354 "
            "SI12600424 DP-126005 | PAY161981 TRF42301241 UTR1819470762096240 2026-10-28 19.10.2026 +44 20 7946 0958")
    assert [m.group(0) for m in find_refs(text)] == ["90031237", "91005413", "MUM/2627/04212", "UK-1043617", "CN-1031273",
                                                     "JP-26-002330", "FA2026-09168", "SRV-100354", "SI12600424", "DP-126005"]


def test_ten_digit_numbers_only_when_allowed():
    assert find_refs("Account 1800012345") == []
    assert [m.group(0) for m in find_refs("1800012345", weak_ok=True)] == ["1800012345"]


def test_iban_check_digits():
    assert valid_iban("GB82 WEST 1234 5698 7654 32")
    assert valid_iban("GB16BARC67159787225212")          # sample R32-0173
    assert not valid_iban("GB16BARC67159787225213")      # one digit changed


# --------------------------------------------------------------------------- amounts
@pytest.mark.parametrize("text, value, cur", [
    ("15.999,58 EUR", "15999.58", "EUR"), ("4.600,00 EUR", "4600.00", "EUR"), ("11 353,25 EUR", "11353.25", "EUR"),
    ("3'797.48 CHF", "3797.48", "CHF"), ("₹3,56,639.73", "356639.73", "INR"), ("Rs. 32,11,468.71", "3211468.71", "INR"),
    ("¥2,079,824", "2079824", "JPY"), ("1,402,390円", "1402390", "JPY"), ("KWD 138.000", "138.000", "KWD"),
    ("KD 1,012.432", "1012.432", "KWD"), ("US$9,757.59", "9757.59", "USD"), ("S$8,300.00", "8300.00", "SGD"),
    ("R$63.245,40", "63245.40", "BRL"), ("€ 7,182.23", "7182.23", "EUR"), ("631,08 €", "631.08", "EUR"),
    ("₩3,438,000", "3438000", "KRW"), ("8,43,003.00 INR", "843003.00", "INR"), ("$15,618.75", "15618.75", "USD"),
])
def test_amount_locales(text, value, cur):
    [a] = find_amounts(text)
    assert (a.value, a.currency, a.negative) == (Decimal(value), cur, False)


@pytest.mark.parametrize("text", ["-1,234.00", "1,234.00-", "(1,234.00)", "1,234.00 CR", "−1,234.00"])
def test_negative_and_credit_formats(text):
    [a] = find_amounts(text)
    assert a.value == Decimal("1234.00") and a.negative


def test_three_decimals_only_for_three_decimal_currencies():
    assert parse_number("1012.432", "KWD") == Decimal("1012.432")
    assert parse_number("1.250", "EUR") == Decimal("1250")


def test_identifiers_dates_and_small_numbers_are_not_amounts():
    text = "Invoice UK-1043617 PAY161981 MUM/2627/04212 on 19.10.2026 and 2026-10-28, 18 Nov 2026, 500 units"
    assert find_amounts(text) == []


# --------------------------------------------------------------------------- dates
@pytest.mark.parametrize("text, expected", [
    ("2026-10-28", date(2026, 10, 28)), ("2026/11/02", date(2026, 11, 2)), ("2026.10.19", date(2026, 10, 19)),
    ("28.10.2026", date(2026, 10, 28)), ("10/28/2026", date(2026, 10, 28)), ("16-Nov-2026", date(2026, 11, 16)),
    ("18 Nov 2026", date(2026, 11, 18)), ("Nov 18, 2026", date(2026, 11, 18)), ("November 02, 2026", date(2026, 11, 2)),
    ("23. Oktober 2026", date(2026, 10, 23)), ("13. März 2026", date(2026, 3, 13)), ("25 octobre 2026", date(2026, 10, 25)),
    ("27 de noviembre de 2026", date(2026, 11, 27)), ("25 de novembro de 2026", date(2026, 11, 25)),
    ("2026年11月27日", date(2026, 11, 27)), ("令和8年11月27日", date(2026, 11, 27)), ("平成30年4月1日", date(2018, 4, 1)),
    ("令和元年5月1日", date(2019, 5, 1)), ("11月25日", date(2026, 11, 25)),
])
def test_fixed_dates(text, expected):
    f = parse_date(text, BASE)
    assert f.value == expected and not f.ambiguous


def test_japanese_month_day_without_year_rolls_into_next_year():
    assert parse_date("1月15日", date(2026, 12, 20)).value == date(2027, 1, 15)


def test_ambiguous_day_month_is_flagged_and_us_preference_used():
    f = parse_date("03/11/2026", BASE)
    assert (f.value, f.ambiguous, f.readings) == (date(2026, 11, 3), True, [date(2026, 3, 11), date(2026, 11, 3)])
    assert parse_date("03/11/2026", BASE, prefer_us=True).value == date(2026, 3, 11)


@pytest.mark.parametrize("text, expected", [
    ("next Friday", date(2026, 10, 30)), ("by end of month", date(2026, 10, 31)), ("end of next month", date(2026, 11, 30)),
    ("within 7 days", date(2026, 11, 4)), ("in 10 days", date(2026, 11, 7)), ("tomorrow", date(2026, 10, 29)),
    ("next week", date(2026, 11, 2)), ("Ende des Monats", date(2026, 10, 31)), ("innerhalb von 14 Tagen", date(2026, 11, 11)),
    ("fin de mois", date(2026, 10, 31)), ("sous 15 jours", date(2026, 11, 12)), ("vendredi prochain", date(2026, 10, 30)),
    ("fin de mes", date(2026, 10, 31)), ("el próximo viernes", date(2026, 10, 30)), ("final do mês", date(2026, 10, 31)),
    ("em 10 dias", date(2026, 11, 7)), ("próxima sexta-feira", date(2026, 10, 30)), ("月末", date(2026, 10, 31)),
    ("来週", date(2026, 11, 2)), ("7日以内", date(2026, 11, 4)),
])
def test_relative_promise_dates_keep_wording(text, expected):
    f = parse_date(f"We will pay {text}.", BASE)
    assert (f.value, f.kind) == (expected, "relative")
    assert f.raw.lower() in text.lower() or text.lower().endswith(f.raw.lower())


def test_dates_in_order_and_relative_needs_base():
    text = "Paid 19.10.2026; the rest end of month."
    assert [f.value for f in find_dates(text, BASE)] == [date(2026, 10, 19), date(2026, 10, 31)]
    assert [f.value for f in find_dates(text)] == [date(2026, 10, 19)]
