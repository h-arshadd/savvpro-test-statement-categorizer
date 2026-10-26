from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_store
from app.parser import MAX_BYTES
from app.rules_store import RulesStore

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "freelancer_card.csv"


def D(value):
    return Decimal(str(value))  # amounts may arrive as strings or numbers


@pytest.fixture
def client(tmp_path):
    store = RulesStore(tmp_path / "rules.json")
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def upload(client, content=None, name="freelancer_card.csv", **params):
    data = SAMPLE.read_bytes() if content is None else content
    return client.post(
        "/api/statements", params=params, files={"file": (name, data, "text/csv")}
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


def test_saving_a_rule_changes_the_next_analysis(client):
    first = {t["row"]: t for t in upload(client).json()["transactions"]}
    assert first[5]["status"] == "needs_review"  # JOES CAFE 9921

    saved = client.post(
        "/api/rules", json={"description": "JOES CAFE 9921", "category": "Meals"}
    )
    assert saved.status_code == 200
    assert saved.json() == {"merchant": "JOES CAFE", "category": "Meals"}

    body = upload(client).json()
    row5 = {t["row"]: t for t in body["transactions"]}[5]
    assert row5["status"] == "categorized"
    assert row5["category"] == "Meals"
    assert body["summary"]["needs_review_count"] == 6
    meals = next(c for c in body["summary"]["categories"] if c["category"] == "Meals")
    assert D(meals["total"]) == Decimal("14.25")


def test_saved_rules_can_be_listed(client):
    client.post("/api/rules", json={"description": "JOES CAFE 9921", "category": "Meals"})
    assert client.get("/api/rules").json() == {"JOES CAFE": "Meals"}


def test_rule_with_unknown_category_is_rejected(client):
    resp = client.post("/api/rules", json={"description": "JOES CAFE", "category": "Yachts"})
    assert resp.status_code == 422


def test_rule_without_a_merchant_is_rejected(client):
    resp = client.post("/api/rules", json={"description": "***", "category": "Meals"})
    assert resp.status_code == 422