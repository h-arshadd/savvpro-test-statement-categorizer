import datetime as dt
from decimal import Decimal
from pathlib import Path

import pytest

from app.categorizer import categorize, categorize_all, summarize
from app.models import RawTransaction, Status
from app.parser import parse_statement
from app.rules import (
    FEES, INCOME, MEALS, NOT_SPENDING, OFFICE, OTHER, PERSONAL, REVIEW_THRESHOLD, SOFTWARE, TRAVEL,
)

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


def test_a_user_choice_beats_the_brain_even_on_a_confident_row():
    adobe = categorize(txn("ADOBE CREATIVE CLOUD", "-59.99"), OFFICE)
    assert adobe.status is Status.CATEGORIZED
    assert adobe.category == OFFICE
    assert adobe.user_set is True
    assert adobe.confidence == 1.0


def test_user_can_mark_a_row_as_personal_and_it_is_left_out():
    r = categorize(txn("JOES CAFE 9921", "-14.25"), PERSONAL)
    assert r.status is Status.EXCLUDED
    assert r.category == PERSONAL


def test_user_can_override_an_excluded_row():
    r = categorize(txn("TRANSFER TO SAVINGS", "-500.00"), OTHER)
    assert r.status is Status.CATEGORIZED
    assert r.category == OTHER


def test_overrides_are_per_row_not_per_merchant():
    d = dt.date(2026, 9, 1)
    rows = [
        txn("AMAZON MKTP US*AAA111", "-87.10", row=2, date=d),
        txn("AMAZON MKTP US*BBB222", "-12.00", row=3, date=d),
    ]
    results = categorize_all(rows, {2: OFFICE})
    assert results[0].status is Status.CATEGORIZED
    assert results[1].status is Status.NEEDS_REVIEW  # same merchant, still asks


def test_overrides_do_not_leak_between_calls():
    rows = [txn("JOES CAFE 9921", "-14.25", row=5)]
    assert categorize_all(rows, {5: MEALS})[0].status is Status.CATEGORIZED
    assert categorize_all(rows)[0].status is Status.NEEDS_REVIEW


def test_user_choice_on_a_duplicate_row_counts_as_a_real_charge():
    d = dt.date(2026, 9, 12)
    rows = [txn("GITHUB INC", "-4.00", row=1, date=d), txn("GITHUB INC", "-4.00", row=2, date=d)]
    results = categorize_all(rows, {2: SOFTWARE})
    assert results[1].status is Status.CATEGORIZED
    assert results[1].duplicate_of is None


# --- Inputs chosen to break the brain: a known word inside something it is not ----------

@pytest.mark.parametrize(
    "description",
    [
        "HILTON GARDEN PIZZA",  # hotel word + food word
        "SLACK BAR AND GRILL",  # software word + food word
        "NOTION COFFEE",
        "AVIS BEAUTY SALON",  # AVIS alone is also a name, not only the car rental
        "AUTOPAY GYM MEMBERSHIP",  # AUTOPAY is how it was paid, not who was paid
    ],
)
def test_a_known_word_inside_a_different_business_is_not_trusted(description):
    r = categorize(txn(description, "-40.00"))
    assert r.status is Status.NEEDS_REVIEW
    assert r.category is None


def test_two_confident_rules_that_disagree_are_not_settled_by_picking_one():
    # Both rules are 0.95 sure on their own. Together they contradict, so ask.
    r = categorize(txn("ZOOM HILTON CONFERENCE", "-300.00"))
    assert r.status is Status.NEEDS_REVIEW
    assert r.category is None
    assert "Software" in r.reason and "Travel" in r.reason


def test_the_real_car_rental_name_still_matches():
    r = categorize(txn("AVIS RENT A CAR 1234", "-210.00"))
    assert r.status is Status.CATEGORIZED
    assert r.category == TRAVEL


def test_conflict_between_two_categories_is_sent_to_review_with_both_named():
    r = categorize(txn("HILTON GARDEN PIZZA", "-30.00"))
    assert "Travel" in r.reason and "Meals" in r.reason


def test_a_longer_phrase_still_beats_its_own_shorter_part():
    r = categorize(txn("AMAZON WEB SERVICES", "-30.00"))
    assert r.category == SOFTWARE
    assert categorize(txn("TRANSFER TO SAVINGS", "-5.00")).status is Status.EXCLUDED


def test_the_word_invoice_alone_is_not_income():
    r = categorize(txn("INVOICE FROM LANDLORD", "2500.00"))
    assert r.category != INCOME
    assert r.status is Status.NEEDS_REVIEW
    assert categorize(txn("INVOICE PAYMENT ACME", "2500.00")).category == INCOME


@pytest.mark.parametrize("description, amount", [("ZOOM", "5000.00"), ("AIRBNB PAYOUT", "900.00")])
def test_money_in_from_a_known_merchant_is_only_a_refund_if_it_says_so(description, amount):
    r = categorize(txn(description, amount))
    assert r.status is Status.NEEDS_REVIEW
    assert r.suggestion is not None
    assert "refund" in r.reason.lower()


@pytest.mark.parametrize("description", ["REFUND ZOOM.US", "ADOBE CREDIT", "ZOOM REVERSAL"])
def test_money_in_that_says_refund_reduces_its_category(description):
    r = categorize(txn(description, "15.99"))
    assert r.status is Status.CATEGORIZED
    assert r.category in (SOFTWARE,)
    assert "reduces" in r.reason


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

def test_personal_rows_are_not_in_any_total():
    rows = [txn("ADOBE CREATIVE CLOUD", "-59.99", row=1), txn("JOES CAFE 9921", "-14.25", row=2)]
    summary = summarize(categorize_all(rows, {2: PERSONAL}))
    assert [c.category for c in summary.categories] == [SOFTWARE]
    assert summary.excluded_count == 1
    assert summary.needs_review_count == 0