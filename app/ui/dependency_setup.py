"""Friendly first-run readiness check for the desktop application."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QMessageBox, QPushButton, QVBoxLayout

from app.setup.runtime_dependencies import check_dependencies, repair_optional_dependencies, browser_runtime_ready


class DependencySetupDialog(QDialog):
    """Keep technical dependency details hidden unless setup genuinely needs attention."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Gmail Organizer — Getting ready")
        self.setMinimumWidth(640)
        layout = QVBoxLayout(self)

        title = QLabel("Getting your Organizer ready")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #F8FAFC;")
        layout.addWidget(title)

        intro = QLabel("The app is checking the built-in features it needs for Gmail, screen control, Windows automation, and browser tasks. You normally do not need to install anything yourself.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #CBD5E1;")
        layout.addWidget(intro)

        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #E2E8F0; background: #1A2231; border: 1px solid #354057; border-radius: 10px; padding: 14px;")
        layout.addWidget(self.status)

        self.fix_button = QPushButton("Set up missing features")
        self.fix_button.clicked.connect(self._repair)
        layout.addWidget(self.fix_button)

        continue_button = QPushButton("Continue")
        continue_button.clicked.connect(self.accept)
        layout.addWidget(continue_button)

        self.setStyleSheet("QDialog { background: #121620; color: #F1F5F9; } QPushButton { color: #F7F8FA; background: #2A3346; border: 1px solid #46516A; border-radius: 8px; padding: 10px 14px; } QPushButton:hover { background: #35415B; }")
        self._refresh()

    def _display_name(self, name: str) -> str:
        return {
            "PySide6": "App interface",
            "Google Gmail": "Gmail connection",
            "Windows input": "Screen and mouse control",
            "Windows UI Automation": "Smart Windows controls",
            "Browser automation": "Browser controls",
        }.get(name, name)

    def _status_text(self) -> str:
        items = check_dependencies()
        lines = []
        for item in items:
            label = self._display_name(item.name)
            if item.available:
                lines.append(f"✓ {label}")
            elif item.required:
                lines.append(f"⚠ {label} needs attention")
            else:
                lines.append(f"○ {label} available when needed")
        if all(item.available or not item.required for item in items):
            if browser_runtime_ready():
                lines.append("\nEverything needed by the current installation is ready.")
            else:
                lines.append("\nThe app can still run. Browser automation may need its optional browser component prepared.")
        return "\n".join(lines)

    def _refresh(self) -> None:
        self.status.setText(self._status_text())
        missing = [item for item in check_dependencies() if not item.available and not item.required]
        self.fix_button.setVisible(bool(missing))

    def _repair(self) -> None:
        self.fix_button.setEnabled(False)
        self.status.setText("Preparing the optional features…\n\nYou do not need to run commands or install packages manually.")
        try:
            actions = repair_optional_dependencies()
            self._refresh()
            detail = "Everything is ready." if not actions else "Optional features were prepared."
            self.status.setText(self._status_text() + f"\n\n{detail}")
        except Exception as exc:
            self._refresh()
            QMessageBox.warning(self, "Setup needs attention", "The app could not finish preparing an optional feature. The rest of the application is still available.\n\n" + str(exc))
        finally:
            self._refresh()
