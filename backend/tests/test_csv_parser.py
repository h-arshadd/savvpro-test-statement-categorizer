import datetime as dt
from decimal import Decimal
from pathlib import Path

import pytest

from app.csv_parser import ParseError, parse_amount, parse_csv
from app.parser import parse_statement

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "freelancer_card.csv"


def amounts(result):
    return [t.amount for t in result.transactions]


def test_basic_rows_and_row_numbers():
    r = parse_csv(b"Date,Description,Amount\n2026-09-01,ADOBE,-59.99\n2026-09-02,REFUND,32.50\n")
    assert amounts(r) == [Decimal("-59.99"), Decimal("32.50")]
    assert r.transactions[0].date == dt.date(2026, 9, 1)
    assert r.transactions[0].row == 2
    assert r.warnings == []


def test_parentheses_currency_and_trailing_minus():
    data = 'Date,Description,Amount\n2026-09-01,STORE,"($1,234.50)"\n2026-09-02,CLIENT,"$2,000.00"\n2026-09-03,FEE,12.50-\n'
    assert amounts(parse_csv(data.encode())) == [Decimal("-1234.50"), Decimal("2000.00"), Decimal("-12.50")]


def test_debit_credit_columns():
    data = "Date,Description,Debit,Credit\n2026-09-01,STORE,50.00,\n2026-09-02,CLIENT,,200.00\n2026-09-03,REFUND,,10.00\n"
    assert amounts(parse_csv(data.encode())) == [Decimal("-50"), Decimal("200"), Decimal("10")]


POSITIVE_PURCHASES = (
    b"Date,Description,Amount\n2026-09-01,ADOBE CREATIVE CLOUD,50.00\n2026-09-02,ZOOM.US,20.00\n"
    b"2026-09-03,PAYMENT THANK YOU,-100.00\n"
)


def test_auto_flips_when_purchases_are_positive():
    r = parse_csv(POSITIVE_PURCHASES)
    assert amounts(r) == [Decimal("-50"), Decimal("-20"), Decimal("100")]
    assert any("flipped" in w for w in r.warnings)


def test_normal_month_with_more_payments_in_than_purchases_is_not_flipped():
    # 3 purchases and 4 client payments. Counting rows would wrongly flip this file.
    data = (
        b"Date,Description,Amount\n"
        b"2026-09-01,ADOBE CREATIVE CLOUD,-59.99\n2026-09-02,DELTA AIR 0062345678912,-412.30\n"
        b"2026-09-03,STAPLES 00123,-42.18\n2026-09-05,CLIENT PAYMENT ACME LLC,2500.00\n"
        b"2026-09-12,CLIENT PAYMENT BETA LLC,1800.00\n2026-09-15,CLIENT PAYMENT GAMMA LLC,900.00\n"
        b"2026-09-20,STRIPE PAYOUT,640.00\n"
    )
    r = parse_csv(data)
    assert amounts(r)[:3] == [Decimal("-59.99"), Decimal("-412.30"), Decimal("-42.18")]
    assert r.warnings == []


def test_unknown_merchants_give_no_evidence_so_signs_are_kept_and_the_user_is_told():
    r = parse_csv(b"Date,Description,Amount\n2026-09-01,ZXQV HOLDINGS,50.00\n2026-09-02,QQQ LTD,20.00\n")
    assert amounts(r) == [Decimal("50.00"), Decimal("20.00")]  # not flipped on a guess
    assert any("Could not tell" in w for w in r.warnings)


def test_forcing_positive_is_expense_flips_without_a_warning():
    r = parse_csv(b"Date,Description,Amount\n2026-09-01,ZXQV HOLDINGS,50.00\n", sign="positive_is_expense")
    assert amounts(r) == [Decimal("-50.00")]
    assert r.warnings == []


def test_sign_override():
    r = parse_csv(POSITIVE_PURCHASES, sign="negative_is_expense")
    assert amounts(r) == [Decimal("50"), Decimal("20"), Decimal("-100")]
    assert r.warnings == []


def test_semicolon_and_european_numbers():
    data = "Date;Description;Amount\n01.09.2026;ZOOM;-15,99\n02.09.2026;CLIENT;1.200,50\n"
    r = parse_csv(data.encode())
    assert amounts(r) == [Decimal("-15.99"), Decimal("1200.50")]
    assert r.transactions[0].date == dt.date(2026, 9, 1)


def test_preamble_before_header():
    data = "Account Statement\nCard ending 1234\nDate,Description,Amount\n2026-09-01,STORE,-5.00\n"
    r = parse_csv(data.encode())
    assert len(r.transactions) == 1
    assert r.transactions[0].row == 4


def test_summary_row_skipped():
    r = parse_csv(b"Date,Description,Amount\n2026-09-01,STORE,-5.00\n,TOTAL,-5.00\n")
    assert len(r.transactions) == 1
    assert any("TOTAL" in w for w in r.warnings)


def test_merchant_starting_with_total_is_kept():
    r = parse_csv(b"Date,Description,Amount\n2026-09-01,TOTAL WINE & MORE,-25.00\n")
    assert len(r.transactions) == 1


def test_bad_amount_rows_are_skipped_with_warning():
    r = parse_csv(b"Date,Description,Amount\n2026-09-01,ADOBE,-5.00\n2026-09-02,WEIRD,abc\n2026-09-03,OTHER,1.2.3\n")
    assert len(r.transactions) == 1
    assert len(r.warnings) == 2
    assert "Row 3" in r.warnings[0]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("59.99 CR", Decimal("59.99")),   # credit: money in
        ("59.99 DR", Decimal("-59.99")),  # debit: money out
        ("USD 12.50", Decimal("12.50")),
        ("-$5.00", Decimal("-5.00")),
    ],
)
def test_amount_markers_are_understood(text, expected):
    assert parse_amount(text) == expected


@pytest.mark.parametrize("text", ["1e5", "12.50 abc", "1.2.3", "N/A"])
def test_amounts_with_stray_letters_are_rejected_not_guessed(text):
    with pytest.raises(ValueError):
        parse_amount(text)


def test_day_first_detected_from_data():
    r = parse_csv(b"Date,Description,Amount\n13/05/2026,A,-1.00\n03/04/2026,B,-2.00\n")
    assert r.transactions[1].date == dt.date(2026, 4, 3)


def test_ambiguous_dates_warn_and_respect_day_first():
    data = b"Date,Description,Amount\n03/04/2026,A,-1.00\n05/06/2026,B,-2.00\n"
    r = parse_csv(data)
    assert r.transactions[0].date == dt.date(2026, 3, 4)
    assert any("ambiguous" in w for w in r.warnings)
    assert parse_csv(data, day_first=True).transactions[0].date == dt.date(2026, 4, 3)


def test_missing_header_raises():
    with pytest.raises(ParseError):
        parse_csv(b"foo,bar\n1,2\n")


def test_unsupported_and_empty_files():
    with pytest.raises(ParseError):
        parse_statement(b"data", "statement.xlsx")
    with pytest.raises(ParseError):
        parse_statement(b"", "statement.csv")


def test_sample_file_parses():
    r = parse_statement(SAMPLE.read_bytes(), SAMPLE.name)
    assert len(r.transactions) == 17
    assert r.warnings == []