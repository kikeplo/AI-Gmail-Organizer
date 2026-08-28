"""Friendly first-run dependency check for the desktop application."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout

from app.setup.runtime_dependencies import check_dependencies, repair_optional_dependencies


class DependencySetupDialog(QDialog):
    """Explain runtime readiness in plain language and offer one-click repair."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Gmail Organizer — Setup check")
        self.setMinimumWidth(640)
        layout = QVBoxLayout(self)
        title = QLabel("Your app is almost ready")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #F8FAFC;")
        layout.addWidget(title)
        intro = QLabel("The Organizer checks the computer-control and browser components it can use. Some features are already built into the app; optional components can be installed automatically.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #CBD5E1;")
        layout.addWidget(intro)
        self.status = QLabel()
        self.status.setText(self._status_text())
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #E2E8F0; background: #1A2231; border: 1px solid #354057; border-radius: 10px; padding: 14px;")
        layout.addWidget(self.status)
        row = QHBoxLayout()
        self.fix_button = QPushButton("Install missing optional components")
        self.fix_button.clicked.connect(self._repair)
        close = QPushButton("Continue")
        close.clicked.connect(self.accept)
        row.addWidget(self.fix_button)
        row.addStretch()
        row.addWidget(close)
        layout.addLayout(row)
        self.setStyleSheet("QDialog { background: #121620; color: #F1F5F9; } QPushButton { color: #F7F8FA; background: #2A3346; border: 1px solid #46516A; border-radius: 8px; padding: 10px 14px; } QPushButton:hover { background: #35415B; }")
        self._update_button_state()

    def _status_text(self) -> str:
        lines = []
        for item in check_dependencies():
            icon = "✓" if item.available else ("⚠" if not item.required else "✗")
            suffix = "required" if item.required else "optional"
            lines.append(f"{icon} {item.name} — {item.detail} ({suffix})")
        return "\n".join(lines)

    def _update_button_state(self) -> None:
        self.fix_button.setEnabled(any(not item.available and not item.required for item in check_dependencies()))

    def _repair(self) -> None:
        self.fix_button.setEnabled(False)
        self.status.setText("Installing optional components…\n\nThis may take a little while. The app will keep your settings and data.")
        try:
            actions = repair_optional_dependencies()
            detail = ", ".join(actions) if actions else "Nothing needed to be installed."
            self.status.setText(self._status_text() + f"\n\nSetup actions: {detail}")
            self._update_button_state()
            QMessageBox.information(self, "Setup check complete", "The application checked the optional components. Restart the app only if a component still shows as unavailable.")
        except Exception as exc:
            self.status.setText(self._status_text())
            self.fix_button.setEnabled(True)
            QMessageBox.warning(self, "Automatic setup could not finish", f"The Organizer could not complete automatic setup.\n\n{exc}\n\nYou can continue using the features that are already available.")
