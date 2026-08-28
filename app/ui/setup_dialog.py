"""First-run and application settings dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout,
)

from app.config.user_settings import (
    CREDENTIALS_FILE,
    install_google_credentials,
    read_config,
    save_api_key,
    save_model,
)


class SetupDialog(QDialog):
    """Collect and edit per-user application settings."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Gmail Organizer — Settings")
        self.setMinimumWidth(600)

        config = read_config()
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.api_key = QLineEdit(config.get("OPENAI_API_KEY", ""))
        self.api_key.setEchoMode(QLineEdit.Password)
        self.api_key.setPlaceholderText("Optional — leave blank to use local command routing")
        form.addRow("OpenAI API key", self.api_key)

        self.model = QLineEdit(config.get("OPENAI_MODEL", ""))
        self.model.setPlaceholderText("Optional model name")
        form.addRow("AI model", self.model)

        oauth_row = QHBoxLayout()
        self.oauth_status = QLineEdit()
        self.oauth_status.setReadOnly(True)
        self.oauth_status.setText(str(CREDENTIALS_FILE) if CREDENTIALS_FILE.exists() else "Not configured")
        browse = QPushButton("Choose OAuth JSON…")
        browse.clicked.connect(self._choose_credentials)
        oauth_row.addWidget(self.oauth_status, 1)
        oauth_row.addWidget(browse)
        form.addRow("Gmail OAuth", oauth_row)
        layout.addLayout(form)

        note = QLineEdit("Settings are stored for this Windows user. They are not part of the GitHub project.")
        note.setReadOnly(True)
        note.setObjectName("settingsNote")
        layout.addWidget(note)

        button_row = QHBoxLayout()
        save = QPushButton("Save")
        save.clicked.connect(self._save)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self._cancel)
        button_row.addStretch()
        button_row.addWidget(cancel)
        button_row.addWidget(save)
        layout.addLayout(button_row)

        self.setStyleSheet("""
            QDialog { background: #121620; color: #F1F5F9; }
            QLabel { color: #E3E8F0; }
            QLineEdit { color: #F7F8FA; background: #202738; border: 1px solid #3A4356; border-radius: 8px; padding: 9px; }
            QLineEdit:focus { border-color: #6D86F7; }
            QPushButton { color: #F7F8FA; background: #2A3346; border: 1px solid #46516A; border-radius: 8px; padding: 9px 14px; }
            QPushButton:hover { background: #35415B; }
            #settingsNote { color: #AAB4C4; background: transparent; border: none; }
        """)

    def _choose_credentials(self) -> None:
        source, _ = QFileDialog.getOpenFileName(
            self, "Select Google OAuth client JSON", "", "JSON files (*.json)"
        )
        if not source:
            return
        try:
            destination = install_google_credentials(source)
            self.oauth_status.setText(str(destination))
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Could not import credentials", str(exc))

    def _save(self) -> None:
        try:
            save_api_key(self.api_key.text())
            save_model(self.model.text())
        except OSError as exc:
            QMessageBox.critical(self, "Could not save settings", str(exc))
            return
        self.accept()

    def _cancel(self) -> None:
        QMessageBox.information(
            self,
            "Setup not completed",
            "No settings were saved. You can open Settings again from the main window at any time.",
        )
        self.reject()
