"""The collapsed form of a docked widget: a pill showing the nearest deadline."""

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .scaling import pill_factor

THICKNESS = 30
PADDING = 14
GAP = 10
MAX_TITLE_WIDTH = 140
COUNTDOWN_TEMPLATE = '00d 00h 00m'  # the widest usual countdown, as format_countdown pads it


class DockPill(QWidget):
    """Horizontal along the top edge; turned so its top faces the screen edge on the sides."""

    hovered = Signal()
    unhovered = Signal()
    pressed = Signal(QPoint)
    moved = Signal(QPoint)
    released = Signal(QPoint)
    menu_requested = Signal(QPoint)

    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edge = 'top'
        self.title, self.countdown, self.color = 'Loading…', '', '#8ea6bd'
        factor = pill_factor()
        self.thickness = round(THICKNESS * factor)
        self.padding, self.gap = round(PADDING * factor), round(GAP * factor)
        self.max_title_width = round(MAX_TITLE_WIDTH * factor)
        self.title_font = QFont('Segoe UI')
        self.title_font.setPointSizeF(9 * factor)
        self.title_font.setWeight(QFont.Weight.DemiBold)
        self.countdown_font = QFont('Consolas')
        self.countdown_font.setPointSizeF(9 * factor)
        self.countdown_font.setWeight(QFont.Weight.DemiBold)

    def set_summary(self, title: str, countdown: str, color: str):
        self.title, self.countdown, self.color = title, countdown, color
        self.update()

    def set_edge(self, edge: str):
        self.edge = edge
        self.update()

    def _title_text(self):
        return QFontMetrics(self.title_font).elidedText(self.title, Qt.TextElideMode.ElideRight,
                                                        self.max_title_width)

    def length(self) -> int:
        """Size along the edge, which fits the text."""
        title = QFontMetrics(self.title_font).horizontalAdvance(self._title_text())
        metrics = QFontMetrics(self.countdown_font)
        # Reserve room for days, so the pill keeps its size when only hours and minutes are left.
        countdown = max(metrics.horizontalAdvance(self.countdown), metrics.horizontalAdvance(COUNTDOWN_TEMPLATE))
        return self.padding * 2 + title + (self.gap + countdown if self.countdown else 0)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Paint in "top edge" coordinates, turned so the pill's top faces the docked edge.
        if self.edge == 'right':
            painter.translate(self.width(), 0)
            painter.rotate(90)
        elif self.edge == 'left':
            painter.translate(0, self.height())
            painter.rotate(-90)
        horizontal = self.edge == 'top'
        length = self.width() if horizontal else self.height()
        thickness = self.height() if horizontal else self.width()
        pen = QPen(QColor(7, 26, 48))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(QColor(23, 58, 99))
        # The top corners sit past the screen edge, so the pill hangs from it.
        painter.drawRoundedRect(QRect(1, -thickness, length - 2, thickness * 2 - 1), thickness / 2, thickness / 2)
        text_area = QRect(self.padding, 0, length - self.padding * 2, thickness)
        painter.setFont(self.title_font)
        painter.setPen(QColor('#e9f1f8'))
        painter.drawText(text_area, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._title_text())
        painter.setFont(self.countdown_font)
        painter.setPen(QColor(self.color))
        painter.drawText(text_area, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self.countdown)
        painter.end()

    def enterEvent(self, event):
        self.hovered.emit()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.unhovered.emit()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.pressed.emit(event.globalPosition().toPoint())
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.moved.emit(event.globalPosition().toPoint())
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.released.emit(event.globalPosition().toPoint())
            event.accept()

    def contextMenuEvent(self, event):
        self.menu_requested.emit(event.globalPos())
