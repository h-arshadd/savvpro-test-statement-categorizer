from app.rules_store import RulesStore


def test_missing_file_means_no_rules(tmp_path):
    assert RulesStore(tmp_path / "rules.json").all() == {}


def test_rules_persist_across_instances(tmp_path):
    path = tmp_path / "nested" / "rules.json"
    RulesStore(path).set("JOES CAFE", "Meals")
    assert RulesStore(path).all() == {"JOES CAFE": "Meals"}


def test_setting_again_overwrites(tmp_path):
    store = RulesStore(tmp_path / "rules.json")
    store.set("JOES CAFE", "Meals")
    store.set("JOES CAFE", "Travel")
    store.set("ZOOM US", "Software & Subscriptions")
    assert store.all() == {"JOES CAFE": "Travel", "ZOOM US": "Software & Subscriptions"}


def test_corrupt_or_wrong_shape_file_is_treated_as_empty(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text("not json at all", encoding="utf-8")
    assert RulesStore(path).all() == {}
    path.write_text("[1, 2]", encoding="utf-8")
    assert RulesStore(path).all() == {}