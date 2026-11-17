"""Edge docking: a widget dragged to a screen edge sticks there and auto-hides.

A docked panel stays on top of other windows. When the cursor leaves it, it
slides off-screen and a pill showing the nearest deadline takes its place on the
edge; hovering or clicking the pill slides the panel back. The position along
the edge is kept, so the panel can sit anywhere on it.
"""

import ctypes
import sys

from PySide6.QtCore import QEasingCurve, QObject, QPoint, QPropertyAnimation, QRect, QTimer, Signal
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QApplication

from .dock_pill import THICKNESS, DockPill
from .preferences import DOCK_EDGES, Placement

SNAP_DISTANCE = 16     # release this close to an edge to dock
HOVER_MARGIN = 8       # the cursor may stray this far outside before the panel collapses
EXPAND_DELAY_MS = 150  # hover delay, so passing the cursor over the pill does nothing
COLLAPSE_DELAY_MS = 500
ANIMATION_MS = 180
TOPMOST_MS = 2000      # other always-on-top windows can cover ours; reclaim the top regularly
DEFAULT_CORNER_GAP = 60

if sys.platform == 'win32':
    from ctypes import wintypes
    _user32 = ctypes.WinDLL('user32')
    _user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                     ctypes.c_int, ctypes.c_int, wintypes.UINT]
    _user32.IsIconic.argtypes = [wintypes.HWND]
    _user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]


def keep_on_top(widget):
    """Move a visible window back to the top of the always-on-top band without activating it."""
    if sys.platform != 'win32' or QGuiApplication.platformName() != 'windows' or not widget.isVisible():
        return
    hwnd = int(widget.winId())
    if _user32.IsIconic(hwnd):  # e.g. after "Show desktop"
        _user32.ShowWindow(hwnd, 4)  # SW_SHOWNOACTIVATE
    # HWND_TOPMOST; SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE | SWP_NOOWNERZORDER
    _user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010 | 0x0200)


def _clamp(value, low, high):
    return max(low, min(value, high))


def docked_position(edge: str, area: QRect, width: int, height: int, anchor: QPoint, expanded: bool) -> QPoint:
    """Top-left of a window docked to ``edge`` of ``area``; ``anchor`` sets the position along the edge.

    Collapsed windows sit just past the edge, entirely off-screen.
    """
    right = area.left() + area.width()
    bottom = area.top() + area.height()
    if edge == 'top':
        x = _clamp(anchor.x(), area.left(), right - width)
        return QPoint(x, area.top() if expanded else area.top() - height)
    y = _clamp(anchor.y(), area.top(), bottom - height)
    if edge == 'left':
        return QPoint(area.left() if expanded else area.left() - width, y)
    return QPoint(right - width if expanded else right, y)


def pill_geometry(edge: str, area: QRect, panel: QRect, length: int, thickness: int = THICKNESS) -> QRect:
    """The pill sits on ``edge``, centred on the expanded ``panel`` and kept inside ``area``."""
    right = area.left() + area.width()
    bottom = area.top() + area.height()
    if edge == 'top':
        x = _clamp(panel.left() + (panel.width() - length) // 2, area.left(), right - length)
        return QRect(x, area.top(), length, thickness)
    y = _clamp(panel.top() + (panel.height() - length) // 2, area.top(), bottom - length)
    return QRect(area.left() if edge == 'left' else right - thickness, y, thickness, length)


def nearest_edge(rect: QRect, area: QRect, allowed=DOCK_EDGES) -> str | None:
    """The edge of ``area`` that ``rect`` touches or overlaps, if within snapping distance."""
    gaps = {'top': rect.top() - area.top(), 'left': rect.left() - area.left(),
            'right': (area.left() + area.width()) - (rect.left() + rect.width())}
    candidates = [(gap, edge) for edge, gap in gaps.items() if edge in allowed and gap <= SNAP_DISTANCE]
    return min(candidates)[1] if candidates else None


def outer_edges(screen) -> tuple[str, ...]:
    """Edges of ``screen`` with no neighbouring monitor, where a hidden panel cannot spill over."""
    geometry = screen.geometry()
    center = geometry.center()
    probes = {'top': QPoint(center.x(), geometry.top() - 1), 'left': QPoint(geometry.left() - 1, center.y()),
              'right': QPoint(geometry.left() + geometry.width(), center.y())}
    return tuple(edge for edge in DOCK_EDGES if QGuiApplication.screenAt(probes[edge]) is None)


class EdgeDock(QObject):
    """Owns the dock state of a frameless top-level widget and its collapsed pill."""

    placement_changed = Signal(object)
    edge_changed = Signal(object)

    def __init__(self, widget):
        super().__init__(widget)
        self.widget = widget
        self.edge = None
        self.expanded = True
        self.screen = None
        self.anchor = QPoint()
        self.dragging = False
        self.pill = DockPill()
        self.pill_press = None
        self.pill_offset = QPoint()
        self.pill_dragging = False
        self.pill.hovered.connect(self.pill_hovered)
        self.pill.unhovered.connect(self.pill_unhovered)
        self.pill.pressed.connect(self.pill_pressed)
        self.pill.moved.connect(self.pill_moved)
        self.pill.released.connect(self.pill_released)
        self.pill.menu_requested.connect(widget.show_context_menu)
        self.animation = QPropertyAnimation(widget, b'pos', self)
        self.animation.setDuration(ANIMATION_MS)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.finished.connect(self.update_pill)
        self.expand_timer = QTimer(self, singleShot=True, interval=EXPAND_DELAY_MS, timeout=self.expand)
        self.collapse_timer = QTimer(self, singleShot=True, interval=COLLAPSE_DELAY_MS, timeout=self.try_collapse)
        self.topmost_timer = QTimer(self, interval=TOPMOST_MS, timeout=self.keep_on_top)
        QGuiApplication.instance().screenRemoved.connect(lambda _screen: self.place())

    # -- state ---------------------------------------------------------------

    def placement(self) -> Placement:
        point = self.anchor if self.edge else self.widget.pos()
        return Placement(point.x(), point.y(), self.edge)

    def area(self) -> QRect:
        if self.screen not in QGuiApplication.screens():
            self.screen = self.widget.screen() or QGuiApplication.primaryScreen()
        return self.screen.availableGeometry()

    def restore(self, placement: Placement | None):
        """Apply a saved placement; by default dock collapsed to the right edge near the top."""
        screen = QGuiApplication.screenAt(QPoint(placement.x, placement.y)) if placement else None
        if screen is None:
            self.screen = QGuiApplication.primaryScreen()
            area = self.screen.availableGeometry()
            # Leave the corner itself free for the caption buttons of maximized windows.
            corner = QPoint(area.left() + area.width() - self.widget.width(), area.top() + DEFAULT_CORNER_GAP)
            if 'right' in outer_edges(self.screen):
                self.dock('right', corner, expanded=False, save=False)
            else:
                self.widget.move(corner.x() - DEFAULT_CORNER_GAP, corner.y())
                self.set_edge(None)
            return
        self.screen = screen
        if placement.edge in outer_edges(screen):
            self.dock(placement.edge, QPoint(placement.x, placement.y), expanded=False, save=False)
        else:
            self.widget.move(placement.x, placement.y)
            self.set_edge(None)

    def dock(self, edge, anchor: QPoint | None = None, screen=None, expanded=None, save=True):
        """Dock to ``edge`` ('top', 'left', 'right') or float freely when ``edge`` is None."""
        if screen is not None:
            self.screen = screen
        elif self.screen is None:
            self.screen = self.widget.screen()
        if edge is None:
            if self.edge is not None:
                self.set_edge(None)
                self.widget.move(self.anchor)  # leave the edge fully on screen
        else:
            self.expanded = self.cursor_inside() if expanded is None else expanded
            self.set_edge(edge)
            self.anchor = docked_position(edge, self.area(), self.widget.width(), self.widget.height(),
                                          anchor if anchor is not None else self.widget.pos(), True)
            self.place()
            if self.expanded:
                self.collapse_timer.start()
        if save:
            self.placement_changed.emit(self.placement())

    def set_edge(self, edge):
        self.animation.stop()
        self.expand_timer.stop()
        self.collapse_timer.stop()
        if edge is None:
            self.expanded = True
            self.topmost_timer.stop()
            self.pill.hide()
        else:
            self.pill.set_edge(edge)
            self.topmost_timer.start()
        if edge != self.edge:
            self.edge = edge
            self.edge_changed.emit(edge)

    def expanded_rect(self) -> QRect:
        size = self.widget.size()
        return QRect(docked_position(self.edge, self.area(), size.width(), size.height(), self.anchor, True), size)

    def place(self, animate=False):
        if self.edge is None or self.dragging:
            return
        target = docked_position(self.edge, self.area(), self.widget.width(), self.widget.height(),
                                 self.anchor, self.expanded)
        self.animation.stop()
        if animate and self.widget.isVisible():
            self.animation.setStartValue(self.widget.pos())
            self.animation.setEndValue(target)
            self.animation.start()
        else:
            self.widget.move(target)
        self.update_pill()

    def update_pill(self):
        """Show the pill once the panel has gone; hide it while the panel is out."""
        if self.edge is None or self.expanded or not self.widget.isVisible():
            self.pill.hide()
            return
        if self.animation.state() == QPropertyAnimation.State.Running or self.pill_dragging:
            return
        self.pill.setGeometry(self.pill_rect())
        if not self.pill.isVisible():
            self.pill.show()
        keep_on_top(self.pill)

    def set_summary(self, title: str, countdown: str, color: str):
        self.pill.set_summary(title, countdown, color)
        self.update_pill()  # the text length sets the pill's size

    def keep_on_top(self):
        if self.busy():
            return  # leave our own menus and dialogs above us
        keep_on_top(self.widget)
        keep_on_top(self.pill)

    def close(self):
        self.topmost_timer.stop()
        self.pill.close()

    # -- hover ---------------------------------------------------------------

    def cursor_inside(self) -> bool:
        cursor = QCursor.pos()
        inside = self.widget.frameGeometry().adjusted(-HOVER_MARGIN, -HOVER_MARGIN, HOVER_MARGIN, HOVER_MARGIN)
        # The pill can be longer than the panel; collapsing there would bring the panel straight back.
        return inside.contains(cursor) or (self.edge is not None and self.pill_rect().contains(cursor))

    def pill_rect(self) -> QRect:
        return pill_geometry(self.edge, self.area(), self.expanded_rect(), self.pill.length(), self.pill.thickness)

    def busy(self) -> bool:
        """A menu or dialog of ours is open; collapsing now would yank the panel away from it."""
        return self.dragging or QApplication.activePopupWidget() is not None or \
            QApplication.activeModalWidget() is not None

    def expand(self, animate=True):
        self.expand_timer.stop()
        if self.edge is not None and not self.expanded and not self.pill_dragging:
            self.expanded = True
            self.place(animate=animate)
            keep_on_top(self.widget)
            # Poll until the cursor has left, even if it never reaches the sliding panel.
            self.collapse_timer.start()

    def collapse(self):
        self.expand_timer.stop()
        self.collapse_timer.stop()
        if self.edge is not None and self.expanded:
            self.expanded = False
            self.place(animate=True)

    def try_collapse(self):
        if self.edge is None or not self.expanded:
            return
        if self.cursor_inside() or self.busy():
            self.collapse_timer.start()
        else:
            self.collapse()

    def entered(self):
        self.collapse_timer.stop()

    def left(self):
        if self.edge is not None and self.expanded:
            self.collapse_timer.start()

    def pill_hovered(self):
        if self.edge is not None and not self.expanded and self.pill_press is None:
            self.expand_timer.start()

    def pill_unhovered(self):
        self.expand_timer.stop()

    # -- dragging ------------------------------------------------------------

    def drag_started(self):
        self.dragging = True
        self.animation.stop()
        self.expand_timer.stop()
        self.collapse_timer.stop()

    def drag_finished(self):
        self.dragging = False
        screen = QGuiApplication.screenAt(QCursor.pos()) or self.widget.screen() or self.screen
        rect = self.widget.frameGeometry()
        self.screen = screen
        edge = nearest_edge(rect, screen.availableGeometry(), outer_edges(screen))
        if edge is None:
            self.set_edge(None)
            self.placement_changed.emit(self.placement())
        else:
            self.dock(edge, rect.topLeft(), screen, expanded=True)

    def pill_pressed(self, position: QPoint):
        self.expand_timer.stop()
        self.pill_press = position
        self.pill_offset = position - self.pill.pos()

    def pill_moved(self, position: QPoint):
        if self.pill_press is None:
            return
        if not self.pill_dragging:
            if (position - self.pill_press).manhattanLength() < QApplication.startDragDistance():
                return
            self.pill_dragging = True
        self.pill.move(position - self.pill_offset)

    def pill_released(self, position: QPoint):
        self.pill_press = None
        if not self.pill_dragging:
            self.expand()  # a click opens the panel straight away
            return
        self.pill_dragging = False
        screen = QGuiApplication.screenAt(position) or self.screen
        pill = self.pill.frameGeometry()
        edge = nearest_edge(pill, screen.availableGeometry(), outer_edges(screen))
        size = self.widget.size()
        # Centre the panel on where the pill was dropped.
        anchor = pill.center() - QPoint(size.width() // 2, size.height() // 2)
        if edge is None:
            self.set_edge(None)
            area = screen.availableGeometry()
            self.widget.move(_clamp(anchor.x(), area.left(), area.left() + area.width() - size.width()),
                             _clamp(anchor.y(), area.top(), area.top() + area.height() - size.height()))
            self.placement_changed.emit(self.placement())
        else:
            self.dock(edge, anchor, screen, expanded=False)
