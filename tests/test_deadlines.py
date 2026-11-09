from datetime import datetime, timedelta, timezone

import pytest

from ccfddl.config import load_catalog
from ccfddl.data import fetch_deadlines, parse_conference, upcoming_deadlines
from ccfddl.deadlines import parse_deadline
from ccfddl.preferences import Preferences, visible_deadlines


def record(key, deadline, year=2026):
    return {"id": key, "title": key.upper(), "tag": "AI", "deadline": deadline, "year": year}


def test_filter_precedes_limit_and_empty_selection_is_respected():
    now = datetime.now(timezone.utc)
    keys = ("aaai", "icml", "icse", "ccs", "cvpr", "acl", "ase")
    data = [record(key, now + timedelta(days=i)) for i, key in enumerate(keys, 1)]
    assert [item["id"] for item in visible_deadlines(data, Preferences(frozenset({"aaai"})))] == list(keys[1:6])
    assert visible_deadlines(data, Preferences(frozenset(keys))) == []
    assert len(visible_deadlines(data, Preferences())) == 5


@pytest.mark.parametrize("zone,offset", [("AoE", -12), ("UTC+8", 8), ("UTC-5.5", -5.5)])
def test_upstream_timezones(zone, offset):
    deadline = parse_deadline("2027-02-03 23:59:59", zone)
    assert deadline.utcoffset() == timedelta(hours=offset)


def test_tbd_and_pacific_daylight_saving():
    assert parse_deadline("TBD", "AoE") is None
    assert parse_deadline("2027-07-01 12:00:00", "PT").utcoffset() == timedelta(hours=-7)
    assert parse_deadline("2027-01-01 12:00:00", "PT").utcoffset() == timedelta(hours=-8)


def test_estimate_leap_day_and_keep_exact_multiple_rounds():
    now = datetime(2026, 11, 9, tzinfo=timezone.utc)
    records = [record("old", datetime(2024, 2, 29, tzinfo=timezone.utc), 2024),
               record("new", datetime(2027, 1, 1, tzinfo=timezone.utc)),
               record("new", datetime(2027, 2, 1, tzinfo=timezone.utc))]
    result = upcoming_deadlines(records, now)
    assert len(result) == 3
    estimate = next(item for item in result if item["id"] == "old")
    assert estimate["est"] is True
    assert estimate["deadline"] == datetime(2027, 2, 28, tzinfo=timezone.utc)
    assert estimate["year"] == 2027
    assert all(not item.get("est") for item in result if item["id"] == "new")


def test_yaml_tags_and_categories_reach_records():
    catalog = load_catalog()
    venue = next(c for c in catalog.conferences if c.id == "ccs")
    document = [{"title": "CCS", "rank": {"core": "A*", "ccf": "A"}, "confs": [
        {"year": 2027, "timezone": "AoE", "timeline": [{"deadline": "TBD"},
         {"deadline": "2027-04-01 23:59:59"}]}]}]
    records = parse_conference(document, venue)
    assert len(records) == 1
    assert records[0]["category"] == "SC"
    assert records[0]["tag"] == "SC"
    assert records[0]["ccf_rank"] == "A"
    document[0]["rank"]["core"] = "A"
    with pytest.raises(ValueError, match="rank"):
        parse_conference(document, venue)


def test_partial_network_failure_keeps_successful_venues(monkeypatch):
    import requests
    import ccfddl.data as module
    catalog = load_catalog()
    now = datetime.now(timezone.utc)

    def fetch(venue):
        if venue.id == "icse":
            raise requests.Timeout("test outage")
        return [record(venue.id, now + timedelta(days=10))]

    monkeypatch.setattr(module, "fetch_conference", fetch)
    records, failures = fetch_deadlines(catalog)
    assert set(failures) == {"icse"}
    assert {item["id"] for item in records} == catalog.ids - {"icse"}


def test_total_network_failure_is_reported(monkeypatch):
    import requests
    import ccfddl.data as module

    def fail(_venue):
        raise requests.Timeout("offline")

    monkeypatch.setattr(module, "fetch_conference", fail)
    with pytest.raises(RuntimeError, match="offline"):
        fetch_deadlines(load_catalog())
