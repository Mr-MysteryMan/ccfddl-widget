"""Load the editable conference catalog and resolve bundled resources."""

from dataclasses import dataclass, field, asdict
from pathlib import Path, PurePosixPath
import re
import sys
import sysconfig

import yaml

DATA_REFRESH_MS = 24 * 60 * 60 * 1000
COUNTDOWN_REFRESH_MS = 60 * 1000
MAX_DEADLINES = 5
DATA_URL = "https://raw.githubusercontent.com/ccfddl/ccf-deadlines/main/"

CATEGORY_COLORS = {
    "AI": {"bg": "#2b6cce", "fg": "#ffffff"},
    "RO": {"bg": "#d46d28", "fg": "#ffffff"},
    "CM": {"bg": "#6e7782", "fg": "#ffffff"},
    "SE": {"bg": "#1c8541", "fg": "#ffffff"},
    "SC": {"bg": "#c44734", "fg": "#ffffff"},
}


@dataclass(frozen=True)
class Conference:
    id: str
    title: str
    category: str
    tag: str
    source: str = ""
    core_rank: str = "A*"


@dataclass(frozen=True)
class Catalog:
    conferences: tuple[Conference, ...]
    categories: dict[str, str]
    category_colors: dict[str, dict[str, str]] = field(default_factory=dict)
    tags: tuple[str, ...] = ()

    @property
    def ids(self) -> set[str]:
        return {conference.id for conference in self.conferences}

    def colors_for(self, category: str) -> dict[str, str]:
        return self.category_colors.get(category, CATEGORY_COLORS.get(category, CATEGORY_COLORS['CM']))


def catalog_document(catalog: Catalog) -> dict:
    return {"version": 1, "categories": dict(catalog.categories),
            "category_colors": catalog.category_colors, "tags": list(catalog.tags),
            "conferences": [asdict(conference) for conference in catalog.conferences]}


def validate_catalog(catalog: Catalog) -> Catalog:
    return catalog_from_document(catalog_document(catalog))


def catalog_path() -> Path:
    if getattr(sys, "frozen", False):
        external = Path(sys.executable).parent / "conferences.yaml"
        if external.is_file():
            return external
        return Path(sys._MEIPASS) / "conferences.yaml"
    source = Path(__file__).resolve().parents[2] / "conferences.yaml"
    if source.is_file():
        return source
    installed = Path(sysconfig.get_path('data')) / 'share' / 'ccfddl-desktop-widget' / 'conferences.yaml'
    return installed if installed.is_file() else source


def load_catalog(path: Path | None = None) -> Catalog:
    path = path or catalog_path()
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return catalog_from_document(document)


def catalog_from_document(document) -> Catalog:
    if not isinstance(document, dict) or document.get("version") != 1:
        raise ValueError("Catalog version must be 1")
    categories = document.get("categories")
    entries = document.get("conferences")
    if not isinstance(categories, dict) or not categories or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in categories.items()
    ):
        raise ValueError("Categories must map IDs to display names")
    if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,11}', key) or not label.strip()
           for key, label in categories.items()):
        raise ValueError("Category IDs must be 1-12 letters, numbers, underscores or hyphens")
    if not isinstance(entries, list):
        raise ValueError("Conferences must be a list")
    colors = document.get('category_colors', {})
    if not isinstance(colors, dict):
        raise ValueError("Category colors must be a mapping")
    for category, palette in colors.items():
        if category not in categories or not isinstance(palette, dict) or any(
            not isinstance(palette.get(key), str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', palette[key])
            for key in ('bg', 'fg')
        ):
            raise ValueError(f"Invalid category color: {category}")
    tags = document.get('tags', [])
    if not isinstance(tags, list) or any(not isinstance(tag, str) or not tag.strip() for tag in tags):
        raise ValueError("Tags must be nonempty text")
    if len(tags) != len(set(tags)):
        raise ValueError("Duplicate tags")
    tags = list(tags)
    conferences = []
    seen_ids, seen_sources, seen_titles = set(), set(), set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Each conference must be a mapping")
        fields = ("id", "title", "category", "tag")
        if any(not isinstance(entry.get(key), str) or not entry[key].strip() for key in fields):
            raise ValueError(f"Conference requires text fields: {', '.join(fields)}")
        if not isinstance(entry.get('source', ''), str) or not isinstance(entry.get('core_rank', 'A*'), str):
            raise ValueError("Conference source and CORE rank must be text")
        conference = Conference(**{key: entry[key].strip() for key in fields},
                                source=entry.get('source', '').strip(), core_rank=entry.get('core_rank', 'A*'))
        source = PurePosixPath(conference.source)
        if conference.source and (source.is_absolute() or ".." in source.parts or "\\" in conference.source
                or len(source.parts) != 3 or source.parts[0] != "conference"
                or source.suffix not in (".yml", ".yaml")):
            raise ValueError(f"Invalid conference source: {conference.source}")
        if conference.category not in categories:
            raise ValueError(f"Unknown category: {conference.title}")
        if conference.id in seen_ids or (conference.source and conference.source in seen_sources):
            raise ValueError(f"Duplicate conference ID or source: {conference.id}")
        if conference.title.casefold() in seen_titles:
            raise ValueError(f"Duplicate conference name: {conference.title}")
        seen_ids.add(conference.id)
        seen_titles.add(conference.title.casefold())
        if conference.source:
            seen_sources.add(conference.source)
        if conference.tag not in tags:
            tags.append(conference.tag)
        conferences.append(conference)
    return Catalog(tuple(conferences), dict(categories), dict(colors), tuple(tags))
