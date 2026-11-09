"""One conference deadline row."""

import webbrowser
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QCursor
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QSizePolicy
from .config import CATEGORY_COLORS
from .deadlines import format_countdown, countdown_color

class ConferenceRow(QWidget):

    def __init__(self, conference: dict, parent=None):
        super().__init__(parent)
        self.conference = conference
        self.deadline = conference.get('deadline')
        self.link = conference.get('link', '')
        note = """Estimated from a past edition; verify the official CFP.
""" if conference.get('est') else ''
        tooltip = note + self.deadline.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z') if self.deadline else conference.get('none_reason', '没有可用的截止日期。')
        self.setToolTip(tooltip)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(3)
        self.name_label = QLabel()
        self.name_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        font = QFont('Segoe UI', 10)
        font.setWeight(QFont.Weight.Medium)
        self.name_label.setFont(font)
        self.name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.domain_label = QLabel()
        domain_font = QFont('Consolas', 8)
        domain_font.setWeight(QFont.Weight.Bold)
        self.domain_label.setFont(domain_font)
        self.domain_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.domain_label.setFixedWidth(36)
        self.domain_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.domain_label.setContentsMargins(0, 0, 0, 0)
        self.level_label = QLabel()
        level_font = QFont('Consolas', 8)
        level_font.setWeight(QFont.Weight.Bold)
        self.level_label.setFont(level_font)
        self.level_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.level_label.setMinimumWidth(40)
        self.countdown_label = QLabel()
        countdown_font = QFont('Consolas', 10)
        countdown_font.setWeight(QFont.Weight.DemiBold)
        self.countdown_label.setFont(countdown_font)
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.countdown_label.setMinimumWidth(110)
        layout.addWidget(self.domain_label)
        layout.addSpacing(9)
        layout.addWidget(self.name_label)
        layout.addWidget(self.level_label)
        layout.addWidget(self.countdown_label)
        self.update_countdown()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.link:
                webbrowser.open(self.link)
        super().mousePressEvent(event)

    def update_countdown(self):
        estimated = bool(self.conference.get('est'))
        if self.deadline is None:
            text, color = 'none', '#8ea6bd'
        else:
            text, remaining_minutes = format_countdown(self.deadline, estimated)
            color = countdown_color(remaining_minutes, estimated)
        label_style = f"""
            QLabel {{
                color: {color};
                background: transparent;
                border: none;
            }}
            """
        self.name_label.setStyleSheet(label_style)
        self.countdown_label.setStyleSheet(label_style)
        self.level_label.setStyleSheet(label_style)
        tag = self.conference.get('tag', 'AI')
        category = self.conference.get('category', 'AI')
        tag_colors = self.conference.get('tag_colors') or CATEGORY_COLORS.get(category, CATEGORY_COLORS['CM'])
        pill_style = f"""
            QLabel {{
                color: {tag_colors['fg']};
                background-color: {tag_colors['bg']};
                border: none;
                border-radius: 9px;
                padding: 1px 5px;
            }}
            """
        self.domain_label.setStyleSheet(pill_style)
        self.domain_label.setText(self.domain_label.fontMetrics().elidedText(tag, Qt.TextElideMode.ElideRight, 26))
        self.domain_label.setToolTip(tag)
        core_rank = self.conference.get('core_rank', '')
        ccf_rank = self.conference.get('ccf_rank', '')
        self.level_label.setText(f'{core_rank} | {ccf_rank}' if core_rank or ccf_rank else 'none')
        title = self.conference['title']
        year = self.conference.get('year')
        if year:
            display_name = f'{title} {year}'
        else:
            display_name = title
        self.name_label.setText(display_name)
        self.countdown_label.setText(text)
