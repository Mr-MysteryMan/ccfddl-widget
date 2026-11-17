from datetime import datetime, timedelta, timezone

import pytest

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from ccfddl.config import load_catalog
from ccfddl.dock_pill import THICKNESS, DockPill
from ccfddl.docking import ANIMATION_MS, COLLAPSE_DELAY_MS, docked_position, nearest_edge, pill_geometry
from ccfddl.preferences import Placement, Preferences, load_preferences, save_preferences
from ccfddl.scaling import auto_scale, panel_scale
from ccfddl.settings_dialog import SettingsDialog
from ccfddl.widget import CCFDDLWidget

AREA = QRect(0, 0, 1920, 1040)


def test_docked_position_keeps_offset_along_edge_and_hides_fully():
    anchor = QPoint(300, 500)
    assert docked_position('top', AREA, 400, 250, anchor, True) == QPoint(300, 0)
    assert docked_position('top', AREA, 400, 250, anchor, False) == QPoint(300, -250)
    assert docked_position('right', AREA, 400, 250, anchor, True) == QPoint(1520, 500)
    assert docked_position('right', AREA, 400, 250, anchor, False) == QPoint(1920, 500)
    assert docked_position('left', AREA, 400, 250, anchor, False) == QPoint(-400, 500)
    # Clamped so the expanded panel stays on screen.
    assert docked_position('top', AREA, 400, 250, QPoint(1800, 0), True) == QPoint(1520, 0)
    assert docked_position('right', AREA, 400, 250, QPoint(0, 1000), True) == QPoint(1520, 790)


def test_pill_is_centred_on_panel_and_vertical_on_the_sides():
    panel = QRect(300, 0, 400, 250)
    assert pill_geometry('top', AREA, panel, 200) == QRect(400, 0, 200, THICKNESS)
    side = QRect(1520, 500, 400, 250)
    assert pill_geometry('right', AREA, side, 200) == QRect(1920 - THICKNESS, 525, THICKNESS, 200)
    assert pill_geometry('left', AREA, QRect(0, 0, 400, 100), 200) == QRect(0, 0, THICKNESS, 200)


def test_pill_keeps_hours_and_minutes_in_place_when_days_run_out(app):
    pill = DockPill()
    pill.set_summary('RSS 2027', '17d  4h 30m', '#ffffff')
    with_days = pill.length()
    pill.set_summary('RSS 2027', ' 4h 30m', '#ffffff')
    assert pill.length() == with_days  # same size, and the right-aligned " 4h 30m" ends in the same place
    pill.close()


def test_nearest_edge_snaps_only_close_to_an_allowed_edge():
    assert nearest_edge(QRect(500, 10, 400, 250), AREA) == 'top'
    assert nearest_edge(QRect(500, -40, 400, 250), AREA) == 'top'
    assert nearest_edge(QRect(1515, 400, 400, 250), AREA) == 'right'
    assert nearest_edge(QRect(1515, 5, 400, 250), AREA) == 'right'  # corner: the closer edge wins
    assert nearest_edge(QRect(500, 100, 400, 250), AREA) is None
    assert nearest_edge(QRect(500, 0, 400, 250), AREA, allowed=('right',)) is None


def make_widget(tmp_path):
    widget = CCFDDLWidget(load_catalog(), tmp_path / 'settings.json', auto_refresh=False)
    now = datetime.now(timezone.utc)
    widget.on_data_loaded([{'id': key, 'title': key.upper(), 'tag': 'SE', 'year': 2027,
                            'deadline': now + timedelta(days=days, minutes=30)}
                           for key, days in (('icse', 3), ('ase', 1))])
    widget.restore_placement()
    widget.show()
    QApplication.processEvents()
    return widget


def settle(ms):
    QTest.qWait(ms + 100)


def test_collapsed_pill_shows_nearest_deadline_and_hover_expands(app, tmp_path):
    widget = make_widget(tmp_path)
    QCursor.setPos(10, 10)
    widget.dock.dock('right')
    area = widget.screen().availableGeometry()
    right = area.left() + area.width()
    settle(COLLAPSE_DELAY_MS + ANIMATION_MS)
    pill = widget.dock.pill
    assert not widget.dock.expanded
    assert widget.x() == right  # the panel is entirely off-screen
    assert pill.isVisible() and pill.title == 'ASE 2027' and pill.countdown.split()[0] == '1d'
    assert pill.width() == THICKNESS and pill.height() > THICKNESS  # vertical on the side
    assert pill.geometry().right() == right - 1
    pill.hovered.emit()
    settle(ANIMATION_MS + 150)
    assert widget.dock.expanded and not pill.isVisible()
    assert widget.x() + widget.width() == right
    QCursor.setPos(widget.geometry().center())
    widget.dock.left()  # cursor still over the panel: stays open
    settle(COLLAPSE_DELAY_MS)
    assert widget.dock.expanded
    widget.close()
    assert not pill.isVisible()


def test_top_pill_is_horizontal_and_click_expands(app, tmp_path):
    widget = make_widget(tmp_path)
    QCursor.setPos(10, 500)
    widget.dock.dock('top', expanded=False)
    pill = widget.dock.pill
    assert pill.height() == THICKNESS and pill.width() > THICKNESS
    assert pill.y() == widget.screen().availableGeometry().top()
    pill.pressed.emit(pill.geometry().center())
    pill.released.emit(pill.geometry().center())
    assert widget.dock.expanded
    widget.close()


def test_dragging_pill_moves_it_along_and_between_edges(app, tmp_path):
    widget = make_widget(tmp_path)
    area = widget.screen().availableGeometry()
    right = area.left() + area.width()
    QCursor.setPos(10, 500)
    widget.dock.dock('top', QPoint(area.left(), 0), expanded=False)
    pill = widget.dock.pill
    start = pill.geometry().center()
    pill.pressed.emit(start)
    target = QPoint(right - 5, area.top() + 300)
    pill.moved.emit(target)
    pill.released.emit(target)
    assert widget.dock.edge == 'right' and not widget.dock.expanded
    assert pill.width() == THICKNESS
    assert abs(widget.dock.expanded_rect().center().y() - target.y()) <= THICKNESS
    pill.pressed.emit(pill.geometry().center())
    pill.moved.emit(area.center())
    pill.released.emit(area.center())
    assert widget.dock.edge is None and not pill.isVisible()
    assert area.contains(widget.geometry())
    widget.close()


def test_menu_dialog_keeps_panel_open(app, tmp_path, monkeypatch):
    widget = make_widget(tmp_path)
    QCursor.setPos(10, 500)
    widget.dock.dock('top', expanded=True)
    monkeypatch.setattr(QApplication, 'activeModalWidget', staticmethod(lambda: widget))
    settle(COLLAPSE_DELAY_MS)
    assert widget.dock.expanded
    monkeypatch.undo()
    settle(COLLAPSE_DELAY_MS + ANIMATION_MS)
    assert not widget.dock.expanded
    assert widget.y() + widget.height() == widget.screen().availableGeometry().top()
    widget.close()


def test_drag_release_docks_or_floats(app, tmp_path):
    widget = make_widget(tmp_path)
    area = widget.screen().availableGeometry()
    widget.dock.drag_started()
    widget.move(area.left() + 40, area.top() - 20)
    QCursor.setPos(widget.geometry().center())
    widget.dock.drag_finished()
    assert widget.dock.edge == 'top'
    assert widget.pos() == QPoint(area.left() + 40, area.top())
    widget.dock.drag_started()
    widget.move(area.left() + 40, area.top() + 60)
    widget.dock.drag_finished()
    assert widget.dock.edge is None
    assert widget.pos() == QPoint(area.left() + 40, area.top() + 60)
    widget.close()


def test_placement_survives_restart_and_settings_save(app, tmp_path):
    widget = make_widget(tmp_path)
    widget.dock.dock('right', QPoint(0, 50))
    saved = load_preferences(tmp_path / 'settings.json')[0].placement
    assert saved.edge == 'right' and saved.y == 50
    dialog = SettingsDialog(widget.catalog, widget.preferences)
    assert dialog.preferences().placement == saved
    dialog.close()
    widget.close()
    restarted = make_widget(tmp_path)
    assert restarted.dock.edge == 'right'
    assert not restarted.dock.expanded
    assert restarted.y() == 50
    restarted.dock.dock(None)
    assert restarted.dock.edge is None
    assert restarted.x() + restarted.width() == restarted.screen().availableGeometry().right() + 1
    restarted.close()


def test_first_start_docks_collapsed_on_right_edge_near_top(app, tmp_path):
    widget = CCFDDLWidget(load_catalog(), tmp_path / 'settings.json', auto_refresh=False)
    widget.restore_placement()
    widget.show()
    QApplication.processEvents()
    area = widget.screen().availableGeometry()
    assert widget.dock.edge == 'right' and not widget.dock.expanded
    pill = widget.dock.pill
    assert pill.isVisible() and pill.geometry().right() == area.right()
    panel = widget.dock.expanded_rect()
    assert area.top() < panel.top() <= area.top() + 100
    widget.close()


def test_auto_scale_follows_screen_height():
    assert auto_scale(None) == 1.0
    assert auto_scale(960) == 1.0     # 1440 px at 150% Windows scaling
    assert auto_scale(1080) == 1.0
    assert auto_scale(1440) == 1.5    # 24" 2560×1440 at 100%
    assert auto_scale(2160) == 2.0
    assert auto_scale(5000) == 2.0


def test_expanded_panel_grows_less_than_pill():
    assert panel_scale(1.0) == 1.0
    assert panel_scale(1.5) == pytest.approx(1.35)
    assert panel_scale(2.0) == pytest.approx(1.7)


def test_scale_preference_roundtrip(tmp_path):
    path = tmp_path / 'settings.json'
    save_preferences(path, Preferences(scale=1.25))
    assert load_preferences(path) == (Preferences(scale=1.25), '')
    path.write_text('{"version": 1, "scale": 3}', encoding='utf-8')
    assert load_preferences(path)[1]


def test_invalid_saved_window_falls_back_to_defaults(tmp_path):
    path = tmp_path / 'settings.json'
    path.write_text('{"version": 1, "window": {"x": 1, "y": 2, "edge": "bottom"}}', encoding='utf-8')
    preferences, error = load_preferences(path)
    assert preferences == Preferences() and error
    path.write_text('{"version": 1, "window": {"x": 1, "y": 2}}', encoding='utf-8')
    assert load_preferences(path) == (Preferences(placement=Placement(1, 2)), '')
