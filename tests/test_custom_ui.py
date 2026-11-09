from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QInputDialog

from ccfddl.catalog_editor import CatalogEditor
from ccfddl.config import load_catalog
from ccfddl.conference_row import ConferenceRow
from ccfddl.data import missing_record
from ccfddl.edit_dialogs import CategoryDialog, ConferenceDialog
from ccfddl.preferences import load_preferences
from ccfddl.settings_dialog import SettingsDialog
from ccfddl.widget import CCFDDLWidget


def test_actual_edit_forms_save_custom_catalog_and_none_survives_restart(app, tmp_path, monkeypatch):
    base = load_catalog()
    path = tmp_path / 'settings.json'
    widget = CCFDDLWidget(base, path, auto_refresh=False)
    refreshes = []
    monkeypatch.setattr(widget, 'refresh_data', lambda: refreshes.append(1))

    def edit():
        settings = app.activeModalWidget()
        assert isinstance(settings, SettingsDialog)

        def category():
            dialog = app.activeModalWidget()
            assert isinstance(dialog, CategoryDialog)
            dialog.code.setText('DB')
            dialog.label.setText('数据库')
            dialog.color = '#7566aa'
            dialog.accept()

        QTimer.singleShot(0, category)
        settings.add_category()

        def tag():
            dialog = app.activeModalWidget()
            assert isinstance(dialog, QInputDialog)
            dialog.setTextValue('WEB')
            dialog.accept()

        QTimer.singleShot(0, tag)
        settings.add_tag()
        settings.select_all(False)

        def conference():
            dialog = app.activeModalWidget()
            assert isinstance(dialog, ConferenceDialog)
            dialog.title.setText('NoSuchConfForTest')
            dialog.category.setCurrentIndex(dialog.category.findData('DB'))
            dialog.tag.setCurrentText('WEB')
            dialog.accept()

        QTimer.singleShot(0, conference)
        settings.add_conference()
        settings.accept()

    QTimer.singleShot(0, edit)
    widget.open_settings()
    assert refreshes == [1]
    custom = next(c for c in widget.catalog.conferences if c.title == 'NoSuchConfForTest')
    assert (custom.category, custom.tag) == ('DB', 'WEB')
    assert load_preferences(path)[0].catalog == widget.catalog
    widget.on_data_loaded([missing_record(custom, '未找到会议')])
    row = widget.content_layout.itemAt(0).widget()
    assert isinstance(row, ConferenceRow) and row.countdown_label.text() == 'none'
    assert '#7566aa' in row.domain_label.styleSheet()
    widget.update_countdowns()
    assert len(widget.data) == 1

    def inspect_status():
        dialog = app.activeModalWidget()
        assert dialog.items[custom.id].text(2) == 'none'
        dialog.reject()

    QTimer.singleShot(0, inspect_status)
    widget.open_settings()
    restarted = CCFDDLWidget(base, path, auto_refresh=False)
    assert restarted.catalog == widget.catalog
    restarted.on_data_loaded([missing_record(custom, '未找到会议')])
    assert restarted.content_layout.itemAt(0).widget().countdown_label.text() == 'none'
    restarted.close()
    widget.close()


def test_cancelling_catalog_edits_leaves_default_catalog_and_settings_untouched(app, tmp_path):
    base = load_catalog()
    path = tmp_path / 'settings.json'
    widget = CCFDDLWidget(base, path, auto_refresh=False)

    def edit_then_cancel():
        dialog = app.activeModalWidget()
        dialog.apply_change(lambda: dialog.editor.add_category('DB', '数据库', '#123456'))
        dialog.apply_change(lambda: dialog.editor.add_conference('WWW', 'DB', 'WEB'))
        dialog.reject()

    QTimer.singleShot(0, edit_then_cancel)
    widget.open_settings()
    assert widget.catalog == base and 'DB' not in base.categories
    assert not path.exists()
    widget.close()


def test_catalog_edit_during_refresh_ignores_stale_data_and_queues_new_lookup(app, tmp_path, monkeypatch):
    base = load_catalog()
    widget = CCFDDLWidget(base, tmp_path / 'settings.json', auto_refresh=False)

    class Worker:
        def deleteLater(self):
            pass

    widget.worker = Worker()
    widget.worker_catalog = base
    editor = CatalogEditor(base)
    editor.edit_conference('icse', 'NoSuchConference', 'SE', 'SE')
    widget.apply_catalog(editor.catalog)
    assert widget._refresh_pending
    widget.on_worker_data([{'id': 'icse', 'deadline': None, 'title': 'old ICSE'}], {})
    assert all(item['title'] != 'old ICSE' for item in widget.data)
    refreshes = []
    monkeypatch.setattr(widget, 'refresh_data', lambda: refreshes.append(1))
    widget.on_worker_finished()
    app.processEvents()
    assert refreshes == [1] and widget.worker is None
    widget.close()
