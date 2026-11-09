"""Fetch configured venues and convert upstream YAML into deadline records."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime, timezone
from urllib.parse import quote

import requests
import yaml

from .config import Catalog, Conference, DATA_URL
from .deadlines import parse_deadline
from .lookup import ConferenceNotFound, conference_paths, resolve_source
from .preferences import deadline_sort_key


def missing_record(conference: Conference, reason: str, pending: bool = False) -> dict:
    return {'id': conference.id, 'title': conference.title, 'category': conference.category,
            'tag': conference.tag, 'deadline': None, 'year': None, 'link': '',
            'core_rank': '', 'ccf_rank': '', 'none_reason': reason, 'lookup_pending': pending}


def parse_conference(document, conference: Conference) -> list[dict]:
    records = []
    documents = document if isinstance(document, list) else [document]
    for item in documents:
        if not isinstance(item, dict):
            continue
        rank = item.get("rank") or {}
        if not isinstance(rank, dict):
            raise ValueError('Invalid upstream ranking data')
        if conference.core_rank and str(rank.get("core", "")).strip() != conference.core_rank:
            raise ValueError(f"Upstream CORE rank is no longer {conference.core_rank}")
        editions = item.get("confs") or []
        if not isinstance(editions, list):
            continue
        for edition in editions:
            if not isinstance(edition, dict):
                continue
            timelines = edition.get("timeline") or []
            if not isinstance(timelines, list):
                continue
            for timeline in timelines:
                if not isinstance(timeline, dict):
                    continue
                deadline = parse_deadline(timeline.get("deadline"), edition.get("timezone", "UTC"))
                if deadline is not None:
                    records.append({"id": conference.id, "title": conference.title,
                                    "category": conference.category, "tag": conference.tag,
                                    "core_rank": str(rank.get('core', '')).strip(),
                                    "ccf_rank": str(rank.get("ccf", "")).strip(),
                                    "year": edition.get("year"), "deadline": deadline,
                                    "link": edition.get("link", "")})
    return records


def upcoming_deadlines(records: list[dict], now: datetime | None = None) -> list[dict]:
    """Preserve the original yearly estimate for venues without a known future CFP."""
    now = now or datetime.now(timezone.utc)
    by_venue = {}
    for record in records:
        by_venue.setdefault(record["id"], []).append(record)
    final = []
    for items in by_venue.values():
        dated = [item for item in items if item.get('deadline') is not None]
        if not dated:
            final.extend(items)
            continue
        upcoming = [item for item in dated if item["deadline"] > now]
        if upcoming:
            final.extend(upcoming)
            continue
        latest = max(dated, key=lambda item: item["deadline"])
        deadline = latest["deadline"]
        years_advanced = 0
        while deadline <= now:
            years_advanced += 1
            try:
                deadline = deadline.replace(year=deadline.year + 1)
            except ValueError:
                deadline = deadline.replace(year=deadline.year + 1, day=28)
        year = latest.get("year")
        if isinstance(year, int):
            year += years_advanced
        final.append({**latest, "year": year, "deadline": deadline, "est": True})
    return sorted(final, key=deadline_sort_key)


def fetch_conference(conference: Conference) -> list[dict]:
    if not conference.source:
        conference = replace(conference, source=resolve_source(conference, conference_paths()))
    response = requests.get(DATA_URL + quote(conference.source, safe="/"),
                            headers={"User-Agent": "CCFDDL-Desktop-Widget"}, timeout=(10, 20))
    if response.status_code == 404:
        raise ConferenceNotFound('数据源中没有该会议的数据文件。')
    response.raise_for_status()
    records = parse_conference(yaml.safe_load(response.text), conference)
    if not records:
        raise ConferenceNotFound("已找到会议，但没有可用的投稿截止日期。")
    return records


def fetch_deadlines(catalog: Catalog) -> tuple[list[dict], dict[str, str]]:
    records, failures = [], {}
    if not catalog.conferences:
        return records, failures
    paths, index_error = [], None
    if any(not conference.source for conference in catalog.conferences):
        try:
            paths = conference_paths()
        except (requests.RequestException, ValueError) as error:
            index_error = str(error)
    resolved = []
    for conference in catalog.conferences:
        if conference.source:
            resolved.append(conference)
        elif index_error is not None:
            failures[conference.id] = f'{conference.title}: {index_error}'
        else:
            try:
                resolved.append(replace(conference, source=resolve_source(conference, paths)))
            except ConferenceNotFound as error:
                records.append(missing_record(conference, str(error)))
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fetch_conference, conference): conference for conference in resolved}
        for future in as_completed(futures):
            conference = futures[future]
            try:
                records.extend(future.result())
            except ConferenceNotFound as error:
                records.append(missing_record(conference, str(error)))
            except (requests.RequestException, yaml.YAMLError, ValueError) as error:
                failures[conference.id] = f"{conference.title}: {error}"
    if len(failures) == len(catalog.conferences):
        raise RuntimeError("\n".join(failures.values()))
    venues = {conference.id: conference for conference in catalog.conferences}
    for record in records:
        conference = venues[record['id']]
        record.update(category=conference.category, tag=conference.tag,
                      tag_colors=catalog.colors_for(conference.category))
    return upcoming_deadlines(records), failures
