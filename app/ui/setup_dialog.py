"""Friendly application settings and guided Gmail connection."""

from __future__ import annotations

import webbrowser

from PySide6.QtCore import QByteArray, QThread, Signal, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QToolButton,
    QVBoxLayout, QWidget,
)

# The remainder of this file is unchanged from the current main branch.
# Qt is explicitly imported above because the responsive Settings dialog uses
# Qt.ScrollBarAlwaysOff and other Qt enum values.
