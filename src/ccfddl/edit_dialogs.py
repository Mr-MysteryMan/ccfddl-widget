"""Small forms for editing categories and conference assignments."""

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout,
)


def save_buttons(dialog, layout):
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
    buttons.button(QDialogButtonBox.StandardButton.Save).setText('保存')
    buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)


class CategoryDialog(QDialog):
    def __init__(self, parent=None, code='', label='', color='#6e7782'):
        super().__init__(parent)
        self.setWindowTitle('编辑 category' if code else '添加 category')
        self.setMinimumWidth(380)
        self.color = color
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.code = QLineEdit(code)
        self.code.setPlaceholderText('例如 DB、HCI')
        self.code.setMaxLength(12)
        self.label = QLineEdit(label)
        self.label.setPlaceholderText('分类名称')
        self.color_button = QPushButton()
        self.color_button.clicked.connect(self.choose_color)
        self.update_color_button()
        form.addRow('category 代码', self.code)
        form.addRow('名称', self.label)
        form.addRow('标签背景色', self.color_button)
        layout.addLayout(form)
        save_buttons(self, layout)

    def update_color_button(self):
        self.color_button.setText(self.color)
        self.color_button.setStyleSheet(f'background-color: {self.color}; color: #ffffff;')

    def choose_color(self):
        color = QColorDialog.getColor(QColor(self.color), self, '选择分类颜色')
        if color.isValid():
            self.color = color.name()
            self.update_color_button()

    def values(self):
        return self.code.text().strip().upper(), self.label.text().strip(), self.color

    def accept(self):
        if not self.code.text().strip() or not self.label.text().strip():
            QMessageBox.warning(self, '请补全信息', '请填写 category 代码和名称。')
            return
        super().accept()


class ConferenceDialog(QDialog):
    def __init__(self, catalog, parent=None, conference=None):
        super().__init__(parent)
        self.original = conference
        self.setWindowTitle('编辑会议' if conference else '添加会议')
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.title = QLineEdit(conference.title if conference else '')
        self.title.setPlaceholderText('例如 WWW、KDD；不存在的会议将显示 none')
        self.category = QComboBox()
        for code, label in catalog.categories.items():
            self.category.addItem(f'{code} · {label}', code)
        if conference:
            self.category.setCurrentIndex(self.category.findData(conference.category))
        self.tag = QComboBox()
        self.tag.setEditable(True)
        self.tag.addItems(catalog.tags)
        if conference:
            self.tag.setCurrentText(conference.tag)
        self.source = QLineEdit(conference.source if conference else '')
        self.source.setPlaceholderText('留空自动查询；同名会议可指定数据文件以区分')
        form.addRow('会议简称', self.title)
        form.addRow('category', self.category)
        form.addRow('tag（可自行输入）', self.tag)
        form.addRow('数据路径（可选）', self.source)
        layout.addLayout(form)
        tip = QLabel('保存设置后自动查询数据。找不到会议或有效截止日期时显示 none。')
        tip.setWordWrap(True)
        layout.addWidget(tip)
        save_buttons(self, layout)

    def values(self):
        title, source = self.title.text().strip(), self.source.text().strip()
        if self.original and title != self.original.title and source == self.original.source:
            source = ''
        return title, self.category.currentData(), self.tag.currentText().strip(), source

    def accept(self):
        if not self.title.text().strip() or not self.tag.currentText().strip():
            QMessageBox.warning(self, '请补全信息', '请填写会议简称和 tag。')
            return
        super().accept()
