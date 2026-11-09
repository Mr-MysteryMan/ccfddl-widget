from datetime import datetime, timedelta, timezone

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QSpinBox

from ccfddl.config import load_catalog
from ccfddl.conference_row import ConferenceRow
from ccfddl.preferences import Preferences, load_preferences
from ccfddl.settings_dialog import SettingsDialog
from ccfddl.widget import CCFDDLWidget


def deadlines():
    now = datetime.now(timezone.utc)
    return [{"id": key, "title": key.upper(), "tag": "SE", "deadline": now + timedelta(days=i), "year": 2027}
            for i, key in enumerate(("ase", "icse", "fse"), 1)]


def rows(widget):
    return [widget.content_layout.itemAt(i).widget() for i in range(widget.content_layout.count())
            if isinstance(widget.content_layout.itemAt(i).widget(), ConferenceRow)]


def test_context_menu_saves_selection_and_restart_restores_it(app, tmp_path):
    path = tmp_path / "settings.json"
    catalog = load_catalog()
    widget = CCFDDLWidget(catalog, path, auto_refresh=False)
    widget.on_data_loaded(deadlines())

    def choose():
        dialog = app.activeModalWidget()
        assert isinstance(dialog, SettingsDialog)
        dialog.select_all(False)
        dialog.items["icse"].setCheckState(0, Qt.CheckState.Checked)
        dialog.accept()

    menu = widget.create_context_menu()
    assert menu.actions()[0].text() == "设置…"
    QTimer.singleShot(0, choose)
    menu.actions()[0].trigger()
    assert [row.conference["id"] for row in rows(widget)] == ["icse"]
    assert load_preferences(path)[0] == widget.preferences
    restarted = CCFDDLWidget(catalog, path, auto_refresh=False)
    restarted.on_data_loaded(deadlines())
    assert [row.conference["id"] for row in rows(restarted)] == ["icse"]
    restarted.close()
    widget.close()


def test_cancel_does_not_change_saved_settings(app, tmp_path):
    path = tmp_path / "settings.json"
    widget = CCFDDLWidget(load_catalog(), path, auto_refresh=False)

    def cancel():
        dialog = app.activeModalWidget()
        dialog.select_all(False)
        dialog.reject()

    QTimer.singleShot(0, cancel)
    widget.open_settings()
    assert not path.exists()
    assert widget.preferences == Preferences()
    widget.close()


def test_empty_selection_and_expired_row_replacement(app, tmp_path):
    catalog = load_catalog()
    widget = CCFDDLWidget(catalog, tmp_path / "settings.json", auto_refresh=False)
    widget.on_data_loaded(deadlines())
    assert rows(widget)[0].conference["id"] == "ase"
    widget.data[0]["deadline"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    widget.update_countdowns()
    assert rows(widget)[0].conference["id"] == "icse"
    widget.preferences = Preferences(frozenset(catalog.ids))
    widget.render_conferences()
    assert rows(widget) == []
    assert "No conferences selected" in widget.content_layout.itemAt(0).widget().text()
    widget.close()


def test_settings_group_toggle_and_search(app):
    dialog = SettingsDialog(load_catalog(), Preferences())
    assert not dialog.findChildren(QSpinBox)
    dialog.select_all(False)
    group = dialog.tree.topLevelItem(0)
    group.setCheckState(0, Qt.CheckState.Checked)
    for i in range(group.childCount()):
        assert group.child(i).checkState(0) == Qt.CheckState.Checked
    dialog.search.setText("icse")
    assert not dialog.items["icse"].isHidden()
    assert dialog.items["icml"].isHidden()
    dialog.search.clear()
    assert not dialog.items["icml"].isHidden()
    dialog.close()


def test_partial_refresh_keeps_prior_deadlines_for_failed_venue(app, tmp_path):
    widget = CCFDDLWidget(load_catalog(), tmp_path / "settings.json", auto_refresh=False)
    previous = deadlines()
    widget.on_data_loaded(previous)
    widget.on_data_loaded([previous[0]], {"icse": "ICSE: offline"})
    assert {item["id"] for item in widget.data} == {"ase", "icse"}
    assert "1 venues unavailable" in widget.status_label.text()
    widget.close()


def test_rerender_visible_widget_stays_at_five_rows(app, tmp_path):
    widget = CCFDDLWidget(load_catalog(), tmp_path / "settings.json", auto_refresh=False)
    widget.on_data_loaded(deadlines())
    widget.show()
    app.processEvents()
    widget.data = deadlines() * 40
    widget.render_conferences()
    app.processEvents()
    assert widget.content_widget.height() > 0
    assert len(rows(widget)) == 5
    assert rows(widget)[0].isVisible()
    assert widget.height() <= widget.screen().availableGeometry().height()
    widget.close()
