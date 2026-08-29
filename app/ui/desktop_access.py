"""Safe, main-thread desktop access consent dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from app.agent.access import AccessManager


class DesktopAccessDialog(QDialog):
    """Collect desktop permissions before any worker or automation task starts."""

    def __init__(self, access: AccessManager | None = None, parent=None) -> None:
        super().__init__(parent)
        self.access = access or AccessManager()
        self.setWindowTitle("Screen & Desktop Access")
        self.setModal(True)
        self.setWindowModality(Qt.ApplicationModal)
        self.setMinimumWidth(560)
        self.setStyleSheet("""
            QDialog { background: #121620; color: #F1F5F9; }
            QLabel#title { color: #F8FAFC; font-size: 22px; font-weight: 800; }
            QLabel#body, QLabel#note { color: #CBD5E1; font-size: 12px; }
            QCheckBox { color: #EAF0F8; font-size: 13px; spacing: 10px; padding: 8px; }
            QCheckBox::indicator { width: 18px; height: 18px; }
            QPushButton { color: #F7F8FA; background: #2A3346; border: 1px solid #46516A; border-radius: 10px; padding: 10px 16px; }
            QPushButton:hover { background: #35415B; }
            QPushButton#allow { background: #4F6CF7; border: none; font-weight: 700; }
            QPushButton#allow:hover { background: #607BFA; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(12)

        title = QLabel("Screen & Desktop Access")
        title.setObjectName("title")
        layout.addWidget(title)

        body = QLabel(
            "AI Gmail Organizer can work with applications on your Windows desktop. "
            "Choose which capabilities you want to allow. Nothing is captured or controlled while this dialog is open."
        )
        body.setObjectName("body")
        body.setWordWrap(True)
        layout.addWidget(body)

        self.screen = QCheckBox("Allow screen access — take screenshots for visual tasks")
        self.input = QCheckBox("Allow mouse & keyboard control — click, type, scroll, and press keys")
        self.browser = QCheckBox("Allow browser automation — control supported browser sessions")
        snapshot = self.access.snapshot()
        self.screen.setChecked(snapshot.get("screen", False))
        self.input.setChecked(snapshot.get("input", False))
        self.browser.setChecked(snapshot.get("browser", False))
        layout.addWidget(self.screen)
        layout.addWidget(self.input)
        layout.addWidget(self.browser)

        note = QLabel(
            "You can change these permissions later in Settings. Gmail access is separate and always uses Google's sign-in flow."
        )
        note.setObjectName("note")
        note.setWordWrap(True)
        layout.addWidget(note)

        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton("Not now")
        cancel.clicked.connect(self.reject)
        allow = QPushButton("Allow selected access")
        allow.setObjectName("allow")
        allow.clicked.connect(self._allow)
        row.addWidget(cancel)
        row.addWidget(allow)
        layout.addLayout(row)

    def _allow(self) -> None:
        # This handler only persists boolean state. It never invokes automation.
        self.access.grant("screen") if self.screen.isChecked() else self.access.revoke("screen")
        self.access.grant("input") if self.input.isChecked() else self.access.revoke("input")
        self.access.grant("browser") if self.browser.isChecked() else self.access.revoke("browser")
        self.accept()
