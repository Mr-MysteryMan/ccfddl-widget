"""Conference selection and editors for categories, tags, and venues."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
    QTabWidget, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QInputDialog, QMessageBox, QHeaderView,
)

from .catalog_editor import CatalogEditor
from .edit_dialogs import CategoryDialog, ConferenceDialog
from .preferences import Preferences


class SettingsDialog(QDialog):
    def __init__(self, catalog, preferences, parent=None, data_status=None):
        super().__init__(parent)
        self.catalog = catalog
        self.initial_catalog = catalog
        self.editor = CatalogEditor(catalog)
        self._hidden = set(preferences.hidden_conferences)
        self.data_status = data_status or {}
        self.original = preferences
        self.setWindowTitle("设置 · 显示的会议")
        self.resize(700, 640)
        root_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        root_layout.addWidget(self.tabs)
        conference_page = QWidget()
        self.tabs.addTab(conference_page, '会议')
        layout = QVBoxLayout(conference_page)
        layout.addWidget(QLabel("勾选要显示的会议。可添加、编辑或删除会议，点击底部保存后生效。"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索会议名称或分类…")
        self.search.textChanged.connect(self.filter_conferences)
        layout.addWidget(self.search)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["会议", "tag", "数据"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.setColumnWidth(1, 90)
        self.tree.setColumnWidth(2, 100)
        self.tree.itemDoubleClicked.connect(lambda item, _: self.edit_selected_conference() if item.parent() else None)
        self.items = {}
        layout.addWidget(self.tree)
        buttons = QHBoxLayout()
        for label, checked in (("全选", True), ("全不选", False)):
            button = QPushButton(label)
            button.clicked.connect(lambda _=False, value=checked: self.select_all(value))
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)
        edit_buttons = QHBoxLayout()
        for label, callback in (('添加会议', self.add_conference), ('编辑会议', self.edit_selected_conference),
                                ('删除会议', self.delete_selected_conference)):
            button = QPushButton(label)
            button.clicked.connect(callback)
            edit_buttons.addWidget(button)
        edit_buttons.addStretch()
        layout.addLayout(edit_buttons)
        self.category_table = self.manager_page('category', ['代码', '名称', '颜色'],
                                                self.add_category, self.edit_category, self.delete_category)
        self.tag_table = self.manager_page('tag', ['tag', '会议数'],
                                           self.add_tag, self.rename_tag, self.delete_tag)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.button(QDialogButtonBox.StandardButton.Save).setText("保存")
        self.button_box.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        root_layout.addWidget(self.button_box)
        self.rebuild()

    def manager_page(self, title, headers, add, edit, delete):
        page = QWidget()
        layout = QVBoxLayout(page)
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.itemDoubleClicked.connect(lambda _: edit())
        layout.addWidget(table)
        buttons = QHBoxLayout()
        for label, callback in (('添加', add), ('编辑', edit), ('删除', delete)):
            button = QPushButton(label)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.tabs.addTab(page, title)
        return table

    def sync_selection(self):
        self._hidden.difference_update(self.catalog.ids)
        self._hidden.update(key for key, item in self.items.items() if item.checkState(0) != Qt.CheckState.Checked)

    def rebuild(self):
        self.tree.clear()
        self.items = {}
        for category, label in self.catalog.categories.items():
            group = QTreeWidgetItem(self.tree, [f'{label} ({category})'])
            group.setFlags(group.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
            for conference in self.catalog.conferences:
                if conference.category != category:
                    continue
                status, reason = self.data_status.get(conference.id, ('待查询', ''))
                item = QTreeWidgetItem(group, [conference.title, conference.tag, status])
                item.setData(0, Qt.ItemDataRole.UserRole, conference.id)
                item.setToolTip(2, reason)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Unchecked if conference.id in self._hidden else Qt.CheckState.Checked)
                self.items[conference.id] = item
            group.setExpanded(True)
        self.category_table.setRowCount(len(self.catalog.categories))
        for row, (code, label) in enumerate(self.catalog.categories.items()):
            color = self.catalog.colors_for(code)['bg']
            for column, value in enumerate((code, label, color)):
                item = QTableWidgetItem(value)
                if column == 2:
                    item.setBackground(QColor(color))
                    item.setForeground(QColor(self.catalog.colors_for(code)['fg']))
                self.category_table.setItem(row, column, item)
        self.tag_table.setRowCount(len(self.catalog.tags))
        for row, tag in enumerate(self.catalog.tags):
            self.tag_table.setItem(row, 0, QTableWidgetItem(tag))
            self.tag_table.setItem(row, 1, QTableWidgetItem(str(sum(c.tag == tag for c in self.catalog.conferences))))
        self.filter_conferences(self.search.text())

    def apply_change(self, change):
        self.sync_selection()
        result = change()
        self.catalog = self.editor.catalog
        self._hidden.intersection_update(self.catalog.ids | (self.original.hidden_conferences - self.initial_catalog.ids))
        self.rebuild()
        return result

    def run_change(self, change):
        try:
            return self.apply_change(change)
        except ValueError as error:
            QMessageBox.warning(self, '无法修改', str(error))

    def filter_conferences(self, text):
        text = text.casefold().strip()
        for conference in self.catalog.conferences:
            searchable = f"{conference.title} {conference.tag} {self.catalog.categories[conference.category]}"
            self.items[conference.id].setHidden(text not in searchable.casefold())
        for index in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(index)
            group.setHidden(all(group.child(i).isHidden() for i in range(group.childCount())))

    def select_all(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for item in self.items.values():
            item.setCheckState(0, state)

    def preferences(self):
        self.sync_selection()
        catalog = self.catalog if self.catalog != self.initial_catalog or self.original.catalog is not None else None
        return Preferences(frozenset(self._hidden), catalog)

    def selected_conference(self):
        item = self.tree.currentItem()
        if item is not None and item.parent() is not None:
            key = item.data(0, Qt.ItemDataRole.UserRole)
            return next(conference for conference in self.catalog.conferences if conference.id == key)
        return None

    def add_conference(self):
        dialog = ConferenceDialog(self.catalog, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.run_change(lambda: self.editor.add_conference(*dialog.values()))
        dialog.deleteLater()

    def edit_selected_conference(self):
        conference = self.selected_conference()
        if conference is None:
            return
        dialog = ConferenceDialog(self.catalog, self, conference)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.run_change(lambda: self.editor.edit_conference(conference.id, *dialog.values()))
            self.data_status.pop(conference.id, None)
            self.rebuild()
        dialog.deleteLater()

    def delete_selected_conference(self):
        conference = self.selected_conference()
        if conference is not None:
            self.run_change(lambda: self.editor.remove_conference(conference.id))

    def selected_cell(self, table):
        return table.item(table.currentRow(), 0).text() if table.currentRow() >= 0 else None

    def add_category(self):
        dialog = CategoryDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.run_change(lambda: self.editor.add_category(*dialog.values()))
        dialog.deleteLater()

    def edit_category(self):
        code = self.selected_cell(self.category_table)
        if code is None:
            return
        dialog = CategoryDialog(self, code, self.catalog.categories[code], self.catalog.colors_for(code)['bg'])
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.run_change(lambda: self.editor.edit_category(code, *dialog.values()))
        dialog.deleteLater()

    def delete_category(self):
        code = self.selected_cell(self.category_table)
        if code is not None:
            self.run_change(lambda: self.editor.remove_category(code))

    def add_tag(self):
        tag, ok = QInputDialog.getText(self, '添加 tag', 'tag 名称：')
        if ok:
            self.run_change(lambda: self.editor.add_tag(tag))

    def rename_tag(self):
        old = self.selected_cell(self.tag_table)
        if old is None:
            return
        tag, ok = QInputDialog.getText(self, '编辑 tag', 'tag 名称：', text=old)
        if ok:
            self.run_change(lambda: self.editor.rename_tag(old, tag))

    def delete_tag(self):
        tag = self.selected_cell(self.tag_table)
        if tag is not None:
            self.run_change(lambda: self.editor.remove_tag(tag))
