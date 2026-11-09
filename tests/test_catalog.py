from pathlib import Path
import sys

import pytest
import yaml

from ccfddl.config import catalog_path, load_catalog


def test_source_catalog_does_not_depend_on_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    catalog = load_catalog()
    assert {"ccs", "icse", "icml", "cav", "lics"} <= catalog.ids
    assert len(catalog.conferences) == len(catalog.ids)


def test_frozen_catalog_prefers_editable_file_next_to_executable(tmp_path, monkeypatch):
    bundled = tmp_path / "bundle"
    bundled.mkdir()
    executable = tmp_path / "CCFDDLWidget.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundled), raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))
    assert catalog_path() == bundled / "conferences.yaml"
    external = tmp_path / "conferences.yaml"
    external.write_text("version: 1", encoding="utf-8")
    assert catalog_path() == external


def test_duplicate_ids_and_invalid_sources_are_rejected(tmp_path):
    document = yaml.safe_load(catalog_path().read_text(encoding="utf-8"))
    path = tmp_path / "conferences.yaml"
    document["conferences"][1]["id"] = document["conferences"][0]["id"]
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        load_catalog(path)
    document["conferences"][1]["id"] = "valid"
    document["conferences"][0]["source"] = "conference/../not-valid.yml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid"):
        load_catalog(path)
