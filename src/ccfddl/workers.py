"""Run network requests away from the Qt UI thread."""

from PySide6.QtCore import QThread, Signal

from .data import fetch_deadlines


class LoadWorker(QThread):
    data_ready = Signal(object, object)
    failed = Signal(str)

    def __init__(self, catalog, parent=None):
        super().__init__(parent)
        self.catalog = catalog

    def run(self):
        try:
            records, failures = fetch_deadlines(self.catalog)
            self.data_ready.emit(records, failures)
        except Exception as error:
            self.failed.emit(f"{type(error).__name__}: {error}")
