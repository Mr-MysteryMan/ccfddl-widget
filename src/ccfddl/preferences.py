"""Persist per-user conference visibility without changing the shared catalog."""

from dataclasses import dataclass
import json
from pathlib import Path
import tempfile

from .config import MAX_DEADLINES, Catalog, catalog_document, catalog_from_document


@dataclass(frozen=True)
class Preferences:
    hidden_conferences: frozenset[str] = frozenset()
    catalog: Catalog | None = None


def load_preferences(path: Path) -> tuple[Preferences, str]:
    if not path.exists():
        return Preferences(), ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != 1:
            raise ValueError("Unsupported settings format")
        hidden = data.get("hidden_conferences", [])
        if not isinstance(hidden, list) or not all(isinstance(x, str) for x in hidden):
            raise ValueError("Invalid hidden conference list")
        catalog = catalog_from_document(data['catalog']) if data.get('catalog') is not None else None
        return Preferences(frozenset(hidden), catalog), ""
    except (OSError, ValueError) as error:
        return Preferences(), f"Unable to read settings; using defaults: {error}"


def save_preferences(path: Path, preferences: Preferences) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix="settings-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            data = {"version": 1, "hidden_conferences": sorted(preferences.hidden_conferences)}
            if preferences.catalog is not None:
                data['catalog'] = catalog_document(preferences.catalog)
            json.dump(data,
                      stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def visible_deadlines(data: list[dict], preferences: Preferences) -> list[dict]:
    upcoming = sorted((item for item in data if item["id"] not in preferences.hidden_conferences),
                      key=deadline_sort_key)
    return upcoming[:MAX_DEADLINES]


def deadline_sort_key(item):
    # Unknown deadlines follow dated entries and keep their configured order.
    return (item.get('deadline') is None, item.get('deadline'))
