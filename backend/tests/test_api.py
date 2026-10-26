from decimal import Decimal
from pathlib import Path

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.parser import MAX_BYTES

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "freelancer_card.csv"


def D(value):
    return Decimal(str(value))  # amounts may arrive as strings or numbers


@pytest.fixture
def client():
    return TestClient(app)


def upload(client, content=None, name="freelancer_card.csv", overrides=None, **params):
    data = SAMPLE.read_bytes() if content is None else content
    form = {"overrides": json.dumps(overrides)} if overrides is not None else {}
    return client.post(
        "/api/statements", params=params, data=form, files={"file": (name, data, "text/csv")}
    )


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_categories_lists_the_built_in_categories(client):
    cats = client.get("/api/categories").json()
    assert "Travel" in cats
    assert "Income" in cats


def test_upload_sample_statement(client):
    resp = upload(client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["filename"] == "freelancer_card.csv"
    assert len(body["transactions"]) == 17
    assert body["warnings"] == []
    summary = body["summary"]
    assert summary["needs_review_count"] == 7
    assert summary["excluded_count"] == 2
    assert D(summary["income"]) == Decimal("2500.00")
    assert summary["categories"][0]["category"] == "Travel"
    assert D(summary["categories"][0]["total"]) == Decimal("435.70")


def test_unsupported_file_type_is_rejected(client):
    resp = upload(client, b"data", name="statement.xlsx")
    assert resp.status_code == 400
    assert "Unsupported" in resp.json()["detail"]


def test_empty_file_is_rejected(client):
    resp = upload(client, b"")
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


def test_unreadable_csv_is_rejected_with_a_helpful_message(client):
    resp = upload(client, b"foo,bar\n1,2\n", name="x.csv")
    assert resp.status_code == 400
    assert "column headers" in resp.json()["detail"]


def test_oversized_file_is_rejected(client):
    resp = upload(client, b"x" * (MAX_BYTES + 1))
    assert resp.status_code == 400
    assert "too large" in resp.json()["detail"].lower()


def test_missing_file_field_is_a_422(client):
    assert client.post("/api/statements").status_code == 422


def test_invalid_sign_option_is_a_422(client):
    assert upload(client, sign="bogus").status_code == 422


def rows_of(response):
    return {t["row"]: t for t in response.json()["transactions"]}


def test_categories_include_personal_and_other(client):
    cats = client.get("/api/categories").json()
    assert "Personal (not business)" in cats
    assert "Other Business Expense" in cats


def test_fixing_a_review_row_changes_the_totals(client):
    assert rows_of(upload(client))[5]["status"] == "needs_review"  # JOES CAFE 9921

    resp = upload(client, overrides={"5": "Meals"})
    row5 = rows_of(resp)[5]
    assert row5["status"] == "categorized"
    assert row5["category"] == "Meals"
    assert row5["user_set"] is True
    body = resp.json()
    assert body["summary"]["needs_review_count"] == 6
    meals = next(c for c in body["summary"]["categories"] if c["category"] == "Meals")
    assert D(meals["total"]) == Decimal("14.25")


def test_a_fix_applies_to_that_row_only(client):
    # Rows 5 and 10 are both cafes (JOES CAFE, BLUE BOTTLE COFFEE). Fixing one leaves the other.
    rows = rows_of(upload(client, overrides={"5": "Meals"}))
    assert rows[5]["status"] == "categorized"
    assert rows[10]["status"] == "needs_review"


def test_a_confident_wrong_row_can_be_fixed_too(client):
    # Row 4 is a transfer the brain excluded and row 3 an Uber ride it filed under Travel.
    # The user can change both.
    rows = rows_of(upload(client, overrides={"4": "Other Business Expense", "3": "Personal (not business)"}))
    assert rows[4]["status"] == "categorized"
    assert rows[4]["category"] == "Other Business Expense"
    assert rows[3]["status"] == "excluded"
    assert rows[3]["user_set"] is True


def test_personal_rows_are_left_out_of_the_totals(client):
    body = upload(client, overrides={"5": "Personal (not business)"}).json()
    row5 = {t["row"]: t for t in body["transactions"]}[5]
    assert row5["status"] == "excluded"
    assert body["summary"]["excluded_count"] == 3
    assert all(c["category"] != "Personal (not business)" for c in body["summary"]["categories"])


def test_no_fixes_means_no_memory_between_uploads(client):
    upload(client, overrides={"5": "Meals"})
    assert rows_of(upload(client))[5]["status"] == "needs_review"


def test_unknown_category_in_a_fix_is_rejected(client):
    resp = upload(client, overrides={"5": "Yachts"})
    assert resp.status_code == 422
    assert "Yachts" in resp.json()["detail"]


@pytest.mark.parametrize("bad", ["not json", "[1, 2]", '{"abc": "Meals"}', '"Meals"'])
def test_malformed_fixes_are_rejected(client, bad):
    resp = client.post(
        "/api/statements",
        data={"overrides": bad},
        files={"file": ("x.csv", SAMPLE.read_bytes(), "text/csv")},
    )
    assert resp.status_code == 422


def test_confirming_a_duplicate_keeps_it_and_counts_it(client):
    row12 = {t["row"]: t for t in upload(client).json()["transactions"]}[12]
    assert row12["status"] == "needs_review"
    assert row12["duplicate_of"] == 11

    body = upload(client, keep_rows=[12]).json()
    row12 = {t["row"]: t for t in body["transactions"]}[12]
    assert row12["status"] == "categorized"
    assert body["summary"]["needs_review_count"] == 6
    software = next(c for c in body["summary"]["categories"] if c["category"] == "Software & Subscriptions")
    assert D(software["total"]) == Decimal("83.98")  # Adobe 59.99 + Zoom 15.99 + GitHub 4 + 4