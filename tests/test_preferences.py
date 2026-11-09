import json

from ccfddl.preferences import Preferences, load_preferences, save_preferences


def test_preferences_roundtrip_and_new_venues_visible_by_default(tmp_path):
    path = tmp_path / "config" / "settings.json"
    assert load_preferences(path) == (Preferences(), "")
    chosen = Preferences(frozenset({"icml", "ccs"}))
    save_preferences(path, chosen)
    assert load_preferences(path) == (chosen, "")
    assert "new-venue" not in load_preferences(path)[0].hidden_conferences
    assert list(path.parent.glob("*.tmp")) == []


def test_damaged_preferences_fall_back_with_error(tmp_path):
    path = tmp_path / "settings.json"
    for contents in ("broken json", "[]", json.dumps({"version": 1, "hidden_conferences": True})):
        path.write_text(contents, encoding="utf-8")
        preferences, error = load_preferences(path)
        assert preferences == Preferences()
        assert error


def test_old_display_count_does_not_override_five_row_limit(tmp_path):
    from datetime import datetime, timedelta, timezone
    from ccfddl.preferences import visible_deadlines

    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"version": 1, "hidden_conferences": [], "max_deadlines": 0}), encoding="utf-8")
    preferences, error = load_preferences(path)
    now = datetime.now(timezone.utc)
    data = [{"id": str(i), "deadline": now + timedelta(days=i)} for i in range(10)]
    assert not error
    assert len(visible_deadlines(data, preferences)) == 5
