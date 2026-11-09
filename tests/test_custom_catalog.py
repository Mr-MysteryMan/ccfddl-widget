from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from ccfddl.catalog_editor import CatalogEditor
from ccfddl.config import Catalog, Conference, load_catalog
from ccfddl.data import fetch_deadlines, parse_conference, missing_record
from ccfddl.lookup import resolve_source, ConferenceNotFound
from ccfddl.preferences import Preferences, load_preferences, save_preferences, visible_deadlines


def test_categories_tags_and_conferences_roundtrip_without_changing_defaults(tmp_path):
    base = load_catalog()
    editor = CatalogEditor(base)
    editor.add_category('DB', '数据库', '#7566aa')
    editor.add_tag('IR')
    key = editor.add_conference('SIGIR', 'DB', 'IR')
    editor.edit_category('DB', 'DS', '数据科学', '#f0c040')
    editor.rename_tag('IR', 'RET')
    conference = next(c for c in editor.catalog.conferences if c.id == key)
    assert (conference.category, conference.tag, conference.core_rank) == ('DS', 'RET', '')
    assert editor.catalog.colors_for('DS') == {'bg': '#f0c040', 'fg': '#102a49'}
    preferences = Preferences(frozenset({'icml'}), editor.catalog)
    path = tmp_path / 'settings.json'
    save_preferences(path, preferences)
    assert load_preferences(path) == (preferences, '')
    assert 'DS' not in base.categories and 'RET' not in base.tags
    assert len(base.conferences) == 31


def test_edit_reassign_and_remove_without_orphaned_references():
    editor = CatalogEditor(load_catalog())
    editor.add_category('DB', '数据库', '#123456')
    editor.add_tag('DB')
    key = editor.add_conference('WWW', 'DB', 'DB')
    with pytest.raises(ValueError, match='先'):
        editor.remove_category('DB')
    with pytest.raises(ValueError, match='先'):
        editor.remove_tag('DB')
    editor.edit_conference(key, 'WWW', 'AI', 'ML')
    editor.remove_tag('DB')
    editor.remove_category('DB')
    editor.remove_conference(key)
    assert key not in editor.catalog.ids


def test_invalid_edit_is_atomic_and_custom_empty_sources_are_valid():
    editor = CatalogEditor(load_catalog())
    original = editor.catalog
    with pytest.raises(ValueError, match='Duplicate'):
        editor.add_conference('ICML', 'AI', 'ML')
    assert editor.catalog == original
    with pytest.raises(ValueError, match='Invalid conference source'):
        editor.add_conference('BadPath', 'AI', 'AI', 'conference/../bad.yml')
    assert editor.catalog == original
    editor.add_conference('CustomOne', 'AI', 'X')
    editor.add_conference('CustomTwo', 'AI', 'Y')
    assert len(editor.catalog.conferences) == 33


def test_missing_custom_conference_is_none_not_a_total_failure(monkeypatch):
    import ccfddl.data as module
    custom = Conference('unknown', 'NoSuchConf2027', 'AI', 'X', core_rank='')
    monkeypatch.setattr(module, 'conference_paths', lambda: ['conference/DB/www.yml'])
    data, failures = fetch_deadlines(Catalog((custom,), {'AI': 'AI'}))
    assert not failures
    assert len(data) == 1 and data[0]['deadline'] is None
    assert data[0]['title'] == custom.title


def test_http_404_is_none_and_manual_meetings_can_have_other_ranks(monkeypatch):
    import ccfddl.data as module
    custom = Conference('x', 'Example', 'AI', 'X', 'conference/AI/example.yml', core_rank='')

    class NotFoundResponse:
        status_code = 404

    monkeypatch.setattr(module.requests, 'get', lambda *args, **kwargs: NotFoundResponse())
    data, failures = fetch_deadlines(Catalog((custom,), {'AI': 'AI'}))
    assert data[0]['deadline'] is None and not failures
    document = [{'rank': {'core': 'B', 'ccf': 'C'}, 'confs': [{'year': 2027,
        'timeline': [{'deadline': '2027-04-01 23:59:59'}]}]}]
    assert parse_conference(document, custom)[0]['core_rank'] == 'B'


def test_lookup_aliases_and_ambiguous_acronyms():
    assert resolve_source(Conference('n', 'NeurIPS', 'AI', 'ML'), ['conference/AI/nips.yml']) == 'conference/AI/nips.yml'
    assert resolve_source(Conference('a', 'ACM MM', 'AI', 'MM'), ['conference/CG/mm.yml']) == 'conference/CG/mm.yml'
    paths = ['conference/SC/fse.yml', 'conference/SE/fse.yml']
    assert resolve_source(Conference('f', 'FSE', 'SC', 'SC'), paths) == paths[0]
    with pytest.raises(ConferenceNotFound, match='多个'):
        resolve_source(Conference('f', 'FSE', 'CM', 'AP'), paths)


def test_automatic_lookup_checks_index_once_for_multiple_custom_meetings(monkeypatch):
    import ccfddl.data as module
    calls, sources = [], []
    catalog = Catalog((Conference('www', 'WWW', 'AI', 'AI', core_rank=''),
                       Conference('kdd', 'KDD', 'AI', 'ML', core_rank='')), {'AI': 'AI'})

    def index():
        calls.append(1)
        return ['conference/DB/www.yml', 'conference/DB/kdd.yml']

    def fetch(conference):
        sources.append(conference.source)
        return [{'id': conference.id, 'deadline': datetime.now(timezone.utc) + timedelta(days=5)}]

    monkeypatch.setattr(module, 'conference_paths', index)
    monkeypatch.setattr(module, 'fetch_conference', fetch)
    data, failures = fetch_deadlines(catalog)
    assert len(calls) == 1 and len(data) == 2 and not failures
    assert set(sources) == {'conference/DB/www.yml', 'conference/DB/kdd.yml'}


def test_none_sorts_after_dates_and_fills_remaining_five_row_slots():
    now = datetime.now(timezone.utc)
    none = missing_record(Conference('x', 'Unknown', 'AI', 'X'), '未找到')
    dates = [{'id': str(i), 'deadline': now + timedelta(days=i + 1)} for i in range(4)]
    visible = visible_deadlines([none, *reversed(dates)], Preferences())
    assert [record['id'] for record in visible] == ['0', '1', '2', '3', 'x']
    assert visible_deadlines([none], Preferences())[0]['deadline'] is None
