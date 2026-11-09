"""Application entry point."""

import sys

import yaml
from PySide6.QtWidgets import QApplication, QMessageBox

from .config import load_catalog
from .widget import CCFDDLWidget


def main():
    app = QApplication(sys.argv)
    app.setOrganizationName("CCFDDL")
    app.setApplicationName("CCFDDLWidget")
    try:
        catalog = load_catalog()
    except (OSError, ValueError, yaml.YAMLError) as error:
        QMessageBox.critical(None, "会议列表加载失败", str(error))
        return 1
    widget = CCFDDLWidget(catalog)
    app.aboutToQuit.connect(widget.shutdown)
    screen = QApplication.primaryScreen()
    if screen:
        geometry = screen.availableGeometry()
        widget.move(geometry.right() - widget.width() - 30, geometry.top() + 30)
    widget.show()
    return app.exec()
