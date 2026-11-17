"""Application entry point."""

import sys

import yaml
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from .config import load_catalog
from .preferences import default_settings_path, load_preferences
from .scaling import apply_scale
from .widget import CCFDDLWidget


def main():
    QCoreApplication.setOrganizationName("CCFDDL")
    QCoreApplication.setApplicationName("CCFDDLWidget")
    # The interface scale must be set before the QApplication is created.
    apply_scale(load_preferences(default_settings_path())[0].scale)
    app = QApplication(sys.argv)
    try:
        catalog = load_catalog()
    except (OSError, ValueError, yaml.YAMLError) as error:
        QMessageBox.critical(None, "会议列表加载失败", str(error))
        return 1
    widget = CCFDDLWidget(catalog)
    app.aboutToQuit.connect(widget.shutdown)
    widget.restore_placement()
    widget.show()
    return app.exec()
