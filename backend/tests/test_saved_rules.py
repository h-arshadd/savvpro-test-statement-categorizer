"""Saved rules can be listed and removed, and removing one really undoes its effect.

Written from the intended behaviour: a rule the user saved is a decision they can take back.
"""
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_store
from app.rules_store import RulesStore

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data" / "freelancer_card.csv"


@pytest.fixture
def client(tmp_path):
    store = RulesStore(tmp_path / "rules.json")
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def upload(client):
    files = {"file": ("freelancer_card.csv", SAMPLE.read_bytes(), "text/csv")}
    return client.post("/api/statements", files=files).json()


def joes_cafe(body):
    return next(t for t in body["transactions"] if t["description"] == "JOES CAFE 9921")


# --- the store ---

def test_store_delete_removes_only_that_rule(tmp_path):
    path = tmp_path / "rules.json"
    store = RulesStore(path)
    store.set("JOES CAFE", "Meals")
    store.set("ZOOM US", "Software & Subscriptions")

    assert store.delete("JOES CAFE") is True
    assert RulesStore(path).all() == {"ZOOM US": "Software & Subscriptions"}  # persisted


def test_store_delete_unknown_rule_returns_false_and_changes_nothing(tmp_path):
    store = RulesStore(tmp_path / "rules.json")
    store.set("JOES CAFE", "Meals")

    assert store.delete("NOT A RULE") is False
    assert store.all() == {"JOES CAFE": "Meals"}


# --- the API ---

def test_removing_a_saved_rule_puts_the_row_back_in_review(client):
    assert joes_cafe(upload(client))["status"] == "needs_review"

    saved = client.post("/api/rules", json={"description": "JOES CAFE 9921", "category": "Meals"})
    assert saved.json() == {"merchant": "JOES CAFE", "category": "Meals"}
    row = joes_cafe(upload(client))
    assert row["status"] == "categorized"
    assert row["category"] == "Meals"

    removed = client.delete(f"/api/rules/{quote('JOES CAFE', safe='')}")
    assert removed.status_code == 200
    assert client.get("/api/rules").json() == {}

    row = joes_cafe(upload(client))
    assert row["status"] == "needs_review"
    assert row["category"] is None


def test_removing_one_rule_keeps_the_others(client):
    client.post("/api/rules", json={"description": "JOES CAFE 9921", "category": "Meals"})
    client.post("/api/rules", json={"description": "LUCKY DRAGON RESTAURANT", "category": "Meals"})

    client.delete("/api/rules/JOES%20CAFE")

    assert client.get("/api/rules").json() == {"LUCKY DRAGON RESTAURANT": "Meals"}


def test_removing_a_rule_that_does_not_exist_is_a_404(client):
    res = client.delete("/api/rules/NOT%20A%20RULE")
    assert res.status_code == 404
    assert "no saved rule" in res.json()["detail"].lower()


def test_merchant_with_spaces_and_ampersand_can_be_removed(client):
    saved = client.post("/api/rules", json={"description": "BLUE & GOLD CAFE 12", "category": "Meals"})
    merchant = saved.json()["merchant"]
    assert merchant == "BLUE & GOLD CAFE"

    res = client.delete(f"/api/rules/{quote(merchant, safe='')}")

    assert res.status_code == 200
    assert client.get("/api/rules").json() == {}