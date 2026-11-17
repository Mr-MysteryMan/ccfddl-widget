"""Desktop widget, context menu, and refresh lifecycle."""

from dataclasses import replace
from datetime import datetime, timezone
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QActionGroup
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QMenu, QDialog, QMessageBox
from .config import DATA_REFRESH_MS, COUNTDOWN_REFRESH_MS
from .conference_row import ConferenceRow
from .workers import LoadWorker
from .preferences import (default_settings_path, load_preferences, save_preferences, visible_deadlines,
                          deadline_sort_key)
from .scaling import SCALE_CHOICES, auto_scale, primary_logical_height, restart
from .data import missing_record
from .settings_dialog import SettingsDialog
from .docking import EdgeDock, outer_edges
from .deadlines import format_countdown, countdown_color

DOCK_MENU = (('浮动在桌面', None), ('停靠到顶部', 'top'), ('停靠到左侧', 'left'), ('停靠到右侧', 'right'))

class CCFDDLWidget(QWidget):

    def __init__(self, catalog, settings_path=None, auto_refresh=True):
        super().__init__()
        self.base_catalog = catalog
        self.settings_path = settings_path or default_settings_path()
        self.preferences, settings_error = load_preferences(self.settings_path)
        self.catalog = self.preferences.catalog or catalog
        self.data = []
        self.worker = None
        self.worker_catalog = None
        self._refresh_pending = False
        self._closing = False
        self.drag_position = QPoint()
        self.press_position = QPoint()
        self._drag_moved = False
        self.dock = EdgeDock(self)
        self.dock.edge_changed.connect(self.apply_window_flags)
        self.dock.placement_changed.connect(self.save_placement)
        self.apply_window_flags(None)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setMinimumWidth(390)
        self.setup_ui()
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdowns)
        self.countdown_timer.start(COUNTDOWN_REFRESH_MS)
        self.data_timer = QTimer(self)
        self.data_timer.timeout.connect(self.refresh_data)
        self.data_timer.start(DATA_REFRESH_MS)
        if auto_refresh:
            QTimer.singleShot(500, self.refresh_data)
        if settings_error:
            self.status_label.setText('Settings reset · right-click to configure')
            self.status_label.setToolTip(settings_error)

    def apply_window_flags(self, edge):
        """Sit below other windows on the desktop; stay on top while docked so the strip can be hovered."""
        layer = Qt.WindowType.WindowStaysOnTopHint if edge else Qt.WindowType.WindowStaysOnBottomHint
        visible = self.isVisible()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | layer)
        if visible:
            self.show()  # changing window flags hides the window

    def restore_placement(self):
        self.dock.restore(self.preferences.placement)

    def save_placement(self, placement):
        self.preferences = replace(self.preferences, placement=placement)
        try:
            save_preferences(self.settings_path, self.preferences)
        except OSError:
            pass  # the position is a convenience; the next move or settings save retries

    def set_scale(self, scale):
        """Save the interface size and restart, since Qt applies it only at startup."""
        if scale == self.preferences.scale:
            return
        preferences = replace(self.preferences, scale=scale)
        try:
            save_preferences(self.settings_path, preferences)
        except OSError as error:
            QMessageBox.warning(self, '无法保存设置', str(error))
            return
        self.preferences = preferences
        restart()
        QApplication.quit()

    def showEvent(self, event):
        super().showEvent(event)
        self.dock.update_pill()  # a widget restored as docked shows its pill once it is visible

    def setup_ui(self):
        self.setObjectName('mainWidget')
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(15, 12, 15, 12)
        outer_layout.setSpacing(0)
        self.title_label = QLabel('Conference Deadlines')
        title_font = QFont('Segoe UI', 11)
        title_font.setWeight(QFont.Weight.DemiBold)
        self.title_label.setFont(title_font)
        self.title_label.setIndent(0)
        self.title_label.setStyleSheet("""
            QLabel {
                color: #e9f1f8;
                background: transparent;
                border: none;
                padding-bottom: 4px;
            }
            """)
        outer_layout.addWidget(self.title_label)
        self.status_label = QLabel('Loading...')
        self.status_label.setStyleSheet("""
            QLabel {
                color: #7f9bb7;
                background: transparent;
                border: none;
                font-size: 8pt;
                padding-bottom: 5px;
            }
            """)
        outer_layout.addWidget(self.status_label)
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("""
            QWidget {
                background: transparent;
                border: none;
            }
            """)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(1)
        outer_layout.addWidget(self.content_widget)
        self.footer_label = QLabel('Data: ccfddl/ccf-deadlines')
        self.footer_label.setStyleSheet("""
            QLabel {
                color: #68829d;
                background: transparent;
                border: none;
                font-size: 7pt;
                padding-top: 7px;
            }
            """)
        outer_layout.addWidget(self.footer_label)
        self.resize(430, 300)

    def paintEvent(self, event):
        """
        Draw the entire widget background and border manually.

        This is more reliable than using a stylesheet for a
        translucent, frameless top-level window on Windows.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        background_color = QColor(23, 58, 99, 255)
        painter.setBrush(background_color)
        border_color = QColor(7, 26, 48, 255)
        pen = QPen(border_color)
        pen.setWidth(2)
        painter.setPen(pen)
        rect = self.rect()
        rect.adjust(1, 1, -1, -1)
        edge = self.dock.edge
        # Push the docked side's rounded corners past the screen edge so the panel looks attached to it.
        if edge == 'top':
            rect.adjust(0, -12, 0, 0)
        elif edge == 'left':
            rect.adjust(-12, 0, 0, 0)
        elif edge == 'right':
            rect.adjust(0, 0, 12, 0)
        painter.drawRoundedRect(rect, 10, 10)
        painter.end()

    def create_context_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #102a49;
                color: #e6eef6;
                border: 1px solid #46627e;
                padding: 4px;
            }

            QMenu::item {
                padding: 6px 25px 6px 10px;
            }

            QMenu::item:selected {
                background-color: #23476d;
            }
            """)
        settings_action = menu.addAction('设置…')
        settings_action.triggered.connect(self.open_settings)
        refresh_action = menu.addAction('Refresh now')
        refresh_action.triggered.connect(self.refresh_data)
        menu.addSeparator()
        dock_group = QActionGroup(menu)
        allowed = outer_edges(self.dock.screen or self.screen())
        for label, edge in DOCK_MENU:
            action = menu.addAction(label)
            action.setEnabled(edge is None or edge in allowed)
            action.setCheckable(True)
            action.setChecked(self.dock.edge == edge)
            action.triggered.connect(lambda _=False, value=edge: self.dock.dock(value))
            dock_group.addAction(action)
        size_menu = menu.addMenu('界面大小')
        size_group = QActionGroup(size_menu)
        automatic = auto_scale(primary_logical_height())
        for label, scale in ((f'自动（{automatic:.0%}）', None), *((f'{s:.0%}', s) for s in SCALE_CHOICES)):
            action = size_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(self.preferences.scale == scale)
            action.triggered.connect(lambda _=False, value=scale: self.set_scale(value))
            size_group.addAction(action)
        menu.addSeparator()
        exit_action = menu.addAction('Exit')
        exit_action.triggered.connect(QApplication.quit)
        return menu

    def contextMenuEvent(self, event):
        self.show_context_menu(event.globalPos())

    def show_context_menu(self, position):
        menu = self.create_context_menu()
        menu.exec(position)
        menu.deleteLater()

    def open_settings(self):
        self.dock.expand(animate=False)  # the dialog centres on the panel, which may be off-screen
        statuses = {}
        for record in self.data:
            key = record['id']
            if record.get('deadline') is not None:
                statuses[key] = ('已找到', '')
            elif key not in statuses:
                statuses[key] = ('待查询' if record.get('lookup_pending') else 'none', record.get('none_reason', ''))
        dialog = SettingsDialog(self.catalog, self.preferences, self, data_status=statuses)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            preferences = dialog.preferences()
            try:
                save_preferences(self.settings_path, preferences)
            except OSError as error:
                QMessageBox.warning(self, '无法保存设置', str(error))
            else:
                self.preferences = preferences
                self.apply_catalog(preferences.catalog or self.base_catalog)
        dialog.deleteLater()

    def with_metadata(self, records):
        venues = {conference.id: conference for conference in self.catalog.conferences}
        result = []
        for record in records:
            conference = venues.get(record['id'])
            if conference is not None:
                result.append({**record, 'title': conference.title, 'category': conference.category,
                               'tag': conference.tag, 'tag_colors': self.catalog.colors_for(conference.category)})
        return result

    def apply_catalog(self, catalog):
        old = {conference.id: conference for conference in self.catalog.conferences}
        changed = catalog != self.catalog
        self.catalog = catalog
        if changed:
            identity = lambda c: (c.title, c.source, c.core_rank)
            unchanged = {c.id for c in catalog.conferences if c.id in old and identity(c) == identity(old[c.id])}
            cached = [record for record in self.data if record['id'] in unchanged]
            present = {record['id'] for record in cached}
            cached.extend(missing_record(c, '等待查询会议数据。', pending=True)
                          for c in catalog.conferences if c.id not in present)
            self.data = self.with_metadata(cached)
            needs_lookup = any(c.id not in unchanged for c in catalog.conferences)
            if self.worker is not None:
                self._refresh_pending = True
            elif needs_lookup:
                self.refresh_data()
        self.render_conferences()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dock.expand(animate=False)  # clicking the collapsed strip opens it at once
            self.press_position = event.globalPosition().toPoint()
            self.drag_position = self.press_position - self.frameGeometry().topLeft()
            self._drag_moved = False
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            position = event.globalPosition().toPoint()
            if not self._drag_moved:
                if (position - self.press_position).manhattanLength() < QApplication.startDragDistance():
                    return
                self._drag_moved = True
                self.dock.drag_started()
            self.move(position - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drag_moved:
            self._drag_moved = False
            self.dock.drag_finished()  # dock if dropped against a screen edge, otherwise float there
            event.accept()

    def enterEvent(self, event):
        self.dock.entered()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.dock.left()
        super().leaveEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.dock.place()  # the docked position depends on the size

    def refresh_data(self):
        if self._closing or self.worker is not None:
            return
        self.status_label.setText('Updating...')
        self.status_label.setToolTip('')
        self.worker = LoadWorker(self.catalog, self)
        self.worker_catalog = self.catalog
        self.worker.data_ready.connect(self.on_worker_data)
        self.worker.failed.connect(self.on_worker_failed)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.start()

    def on_worker_data(self, data, failures):
        if self.worker_catalog == self.catalog:
            self.on_data_loaded(data, failures)

    def on_worker_failed(self, error):
        if self.worker_catalog == self.catalog:
            self.on_data_failed(error)

    def on_worker_finished(self):
        worker = self.worker
        self.worker = None
        if worker is not None:
            worker.deleteLater()
        if self._refresh_pending and not self._closing:
            self._refresh_pending = False
            QTimer.singleShot(0, self.refresh_data)

    def shutdown(self):
        self._closing = True
        self.data_timer.stop()
        self.countdown_timer.stop()
        self.dock.close()
        if self.worker is not None:
            self.worker.wait()

    def on_data_loaded(self, data, failures=None):
        failures = failures or {}
        previous = [item for item in self.data if item['id'] in failures
                    and (item.get('deadline') is None or item['deadline'] > datetime.now(timezone.utc))]
        previous = [{**item, 'lookup_pending': False, 'none_reason': failures[item['id']]}
                    if item.get('deadline') is None else item for item in previous]
        present = {item['id'] for item in data + previous}
        previous.extend(missing_record(c, failures[c.id]) for c in self.catalog.conferences
                        if c.id in failures and c.id not in present)
        self.data = sorted(self.with_metadata(data + previous), key=deadline_sort_key)
        self.render_conferences()
        now = datetime.now().strftime('%H:%M')
        status = f'Updated {now}'
        if failures:
            status += f' · {len(failures)} venues unavailable'
        self.status_label.setText(status)
        self.status_label.setToolTip('\n'.join(failures.values()))

    def on_data_failed(self, error: str):
        if any(item.get('deadline') is not None for item in self.data):
            self.status_label.setText('Update failed · using previous data')
        else:
            self.status_label.setText('Unable to load data')
        if not self.data:
            self.data = self.with_metadata([missing_record(c, error) for c in self.catalog.conferences])
        else:
            self.data = [{**record, 'lookup_pending': False, 'none_reason': error}
                         if record.get('deadline') is None else record for record in self.data]
        self.status_label.setToolTip(error)
        self.render_conferences()

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
            child_layout = item.layout()
            if child_layout is not None:
                self.clear_layout(child_layout)

    def render_conferences(self):
        self.clear_layout(self.content_layout)
        upcoming = visible_deadlines(self.data, self.preferences)
        if not upcoming:
            selected = self.catalog.ids - self.preferences.hidden_conferences
            message = 'No upcoming deadlines for selected conferences.' if selected else 'No conferences selected · right-click → 设置'
            empty_label = QLabel(message)
            empty_label.setStyleSheet("""
                QLabel {
                    color: #8ea6bd;
                    background: transparent;
                    border: none;
                    padding: 10px 0;
                }
                """)
            self.content_layout.addWidget(empty_label)
            empty_label.show()
        for conference in upcoming:
            row = ConferenceRow(conference)
            self.content_layout.addWidget(row)
            row.show()
        self.content_layout.invalidate()
        self.content_layout.activate()
        self.content_widget.adjustSize()
        self.adjustSize()
        self.update_summary()

    def update_countdowns(self):
        now = datetime.now(timezone.utc)
        previous_count = len(self.data)
        self.data = [item for item in self.data if item.get('deadline') is None
                     or item['deadline'].astimezone(timezone.utc) > now]
        if len(self.data) != previous_count:
            self.render_conferences()
            return
        for i in range(self.content_layout.count()):
            item = self.content_layout.itemAt(i)
            widget = item.widget()
            if isinstance(widget, ConferenceRow):
                widget.update_countdown()
        self.update_summary()

    def update_summary(self):
        """Show the nearest selected deadline on the collapsed pill."""
        nearest = next((item for item in visible_deadlines(self.data, self.preferences)
                        if item.get('deadline') is not None), None)
        if nearest is None:
            selected = self.catalog.ids - self.preferences.hidden_conferences
            self.dock.set_summary('No deadlines' if self.data or not selected else 'Loading…', '', '#8ea6bd')
            return
        estimated = bool(nearest.get('est'))
        text, minutes = format_countdown(nearest['deadline'], estimated)
        title = f"{nearest['title']} {nearest['year']}" if nearest.get('year') else nearest['title']
        # Keep the padding: right-aligned in a monospace font, hours and minutes stay put as days run out.
        self.dock.set_summary(title, text, countdown_color(minutes, estimated))

    def closeEvent(self, event):
        self.dock.close()
        super().closeEvent(event)
