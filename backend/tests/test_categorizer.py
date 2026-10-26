import datetime as dt
from decimal import Decimal
from pathlib import Path

import pytest

from app.categorizer import categorize, categorize_all, summarize
from app.models import RawTransaction, Status
from app.parser import parse_statement
from app.rules import FEES, INCOME, MEALS, NOT_SPENDING, OFFICE, REVIEW_THRESHOLD, SOFTWARE, TRAVEL

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "freelancer_card.csv"


def txn(description, amount, *, row=1, date=None):
    return RawTransaction(row=row, date=date, description=description, amount=Decimal(amount))


@pytest.mark.parametrize(
    "description, amount, category",
    [
        ("ADOBE CREATIVE CLOUD", "-59.99", SOFTWARE),
        ("ZOOM.US 888-799-9666", "-15.99", SOFTWARE),
        ("AMAZON WEB SERVICES", "-30.00", SOFTWARE),
        ("UBER *TRIP HELP.UBER.COM", "-23.40", TRAVEL),
        ("DELTA AIR 0062345678912", "-412.30", TRAVEL),
        ("STAPLES 00123", "-42.18", OFFICE),
        ("INTEREST CHARGE", "-18.40", FEES),
    ],
)
def test_known_merchants_are_categorized(description, amount, category):
    r = categorize(txn(description, amount))
    assert r.status is Status.CATEGORIZED
    assert r.category == category
    assert r.confidence >= REVIEW_THRESHOLD


@pytest.mark.parametrize(
    "description, amount, suggestion",
    [
        ("UBER *EATS PENDING", "-31.20", MEALS),
        ("JOES CAFE 9921", "-14.25", MEALS),
        ("SQ *BLUE BOTTLE COFFEE", "-6.50", MEALS),
        ("LUCKY DRAGON RESTAURANT", "-48.00", MEALS),
        ("AMAZON MKTP US*2K4X91", "-87.10", OFFICE),
        ("OFFICE DEPOTT 0042", "-20.00", OFFICE),  # misspelling: suggest only, never auto-assign
    ],
)
def test_uncertain_rows_go_to_review_with_a_suggestion(description, amount, suggestion):
    r = categorize(txn(description, amount))
    assert r.status is Status.NEEDS_REVIEW
    assert r.category is None
    assert r.suggestion == suggestion
    assert r.reason


def test_unknown_merchant_goes_to_review_without_a_suggestion():
    r = categorize(txn("ZXQV HOLDINGS", "-10.00"))
    assert r.status is Status.NEEDS_REVIEW
    assert r.category is None
    assert r.suggestion is None


@pytest.mark.parametrize(
    "description, amount",
    [
        ("TRANSFER TO SAVINGS", "-500.00"),
        ("TRANSFER FROM SAVINGS", "500.00"),  # money in, but not income
        ("PAYMENT THANK YOU", "1200.00"),
        ("AUTOPAY PAYMENT", "-300.00"),
    ],
)
def test_transfers_and_card_payments_are_excluded(description, amount):
    r = categorize(txn(description, amount))
    assert r.status is Status.EXCLUDED
    assert r.category == NOT_SPENDING


def test_transfer_to_a_person_is_not_assumed_to_be_non_spending():
    r = categorize(txn("TRANSFER TO JOHN SMITH", "-250.00"))
    assert r.status is Status.NEEDS_REVIEW
    assert r.suggestion == NOT_SPENDING


def test_refund_from_known_merchant_stays_in_its_category_not_income():
    r = categorize(txn("REFUND ZOOM.US", "15.99"))
    assert r.status is Status.CATEGORIZED
    assert r.category == SOFTWARE
    assert r.amount == Decimal("15.99")


def test_money_in_from_unknown_source_is_not_assumed_to_be_income():
    r = categorize(txn("ACME MYSTERY", "20.00"))
    assert r.status is Status.NEEDS_REVIEW
    assert r.category is None
    assert "refund" in r.reason.lower()


def test_client_payment_is_income_only_when_money_comes_in():
    incoming = categorize(txn("CLIENT PAYMENT ACME LLC", "2500.00"))
    assert incoming.status is Status.CATEGORIZED
    assert incoming.category == INCOME

    outgoing = categorize(txn("CLIENT PAYMENT ACME LLC", "-2500.00"))
    assert outgoing.status is Status.NEEDS_REVIEW
    assert outgoing.category is None


def test_zero_amount_goes_to_review():
    r = categorize(txn("ADOBE CREATIVE CLOUD", "0.00"))
    assert r.status is Status.NEEDS_REVIEW


def test_saved_rule_decides_and_beats_built_in_rules():
    overrides = {"JOES CAFE": MEALS, "ADOBE CREATIVE CLOUD": OFFICE}

    cafe = categorize(txn("JOES CAFE 9921", "-14.25"), overrides)
    assert cafe.status is Status.CATEGORIZED
    assert cafe.category == MEALS
    assert cafe.confidence == 1.0

    adobe = categorize(txn("ADOBE CREATIVE CLOUD", "-59.99"), overrides)
    assert adobe.category == OFFICE


def test_saved_rule_can_mark_a_merchant_as_not_spending():
    r = categorize(txn("ZXQV HOLDINGS", "-10.00"), {"ZXQV HOLDINGS": NOT_SPENDING})
    assert r.status is Status.EXCLUDED


def test_duplicate_charge_is_flagged_but_first_one_is_kept():
    d = dt.date(2026, 9, 12)
    rows = [
        txn("GITHUB INC", "-4.00", row=1, date=d),
        txn("GITHUB INC", "-4.00", row=2, date=d),
        txn("GITHUB INC", "-4.00", row=3, date=d),
    ]
    results = categorize_all(rows)
    assert results[0].status is Status.CATEGORIZED
    assert results[0].category == SOFTWARE
    for later in results[1:]:
        assert later.status is Status.NEEDS_REVIEW
        assert later.category is None
        assert later.suggestion == SOFTWARE
        assert "duplicate" in later.reason.lower()


def test_similar_rows_that_are_not_duplicates_are_left_alone():
    d = dt.date(2026, 9, 12)
    rows = [
        txn("GITHUB INC", "-4.00", row=1, date=d),
        txn("GITHUB INC", "-4.00", row=2, date=dt.date(2026, 9, 13)),  # other day
        txn("GITHUB INC", "-5.00", row=3, date=d),  # other amount
        txn("GITHUB INC", "-4.00", row=4, date=None),  # no date: cannot tell
        txn("GITHUB INC", "-4.00", row=5, date=None),
    ]
    assert all(r.status is Status.CATEGORIZED for r in categorize_all(rows))


def test_repeated_transfers_are_not_flagged_as_duplicates():
    d = dt.date(2026, 9, 3)
    rows = [txn("TRANSFER TO SAVINGS", "-500.00", row=1, date=d),
            txn("TRANSFER TO SAVINGS", "-500.00", row=2, date=d)]
    assert all(r.status is Status.EXCLUDED for r in categorize_all(rows))


def test_refund_reduces_its_category_total():
    rows = [txn("ZOOM.US 888-799-9666", "-15.99", row=1), txn("REFUND ZOOM.US", "15.99", row=2)]
    summary = summarize(categorize_all(rows))
    software = next(c for c in summary.categories if c.category == SOFTWARE)
    assert software.total == 0
    assert software.count == 2
    assert summary.income == 0


def test_sample_statement_end_to_end():
    parsed = parse_statement(SAMPLE.read_bytes(), SAMPLE.name)
    results = categorize_all(parsed.transactions)
    by_row = {r.row: r for r in results}

    assert len(results) == 17
    assert sum(r.status is Status.CATEGORIZED for r in results) == 8
    assert sum(r.status is Status.EXCLUDED for r in results) == 2
    assert sum(r.status is Status.NEEDS_REVIEW for r in results) == 7

    assert by_row[12].status is Status.NEEDS_REVIEW  # second GITHUB charge
    assert "11" in by_row[12].reason
    assert by_row[7].status is Status.NEEDS_REVIEW  # Amazon money back: business or personal unknown

    summary = summarize(results)
    totals = {c.category: c.total for c in summary.categories}
    assert totals == {
        TRAVEL: Decimal("435.70"),
        SOFTWARE: Decimal("79.98"),
        OFFICE: Decimal("42.18"),
        FEES: Decimal("18.40"),
    }
    assert summary.categories[0].category == TRAVEL  # biggest first
    assert summary.income == Decimal("2500.00")
    assert summary.excluded_count == 2
    assert summary.needs_review_count == 7
    assert summary.needs_review_net == Decimal("158.55")

def test_confirmed_duplicate_is_kept_as_a_normal_charge():
    d = dt.date(2026, 9, 12)
    rows = [
        txn("GITHUB INC", "-4.00", row=1, date=d),
        txn("GITHUB INC", "-4.00", row=2, date=d),
    ]
    flagged = categorize_all(rows)
    assert flagged[1].duplicate_of == 1

    kept = categorize_all(rows, keep_rows=[2])
    assert kept[1].status is Status.CATEGORIZED
    assert kept[1].category == SOFTWARE
    assert kept[1].duplicate_of is None