"""First-run configuration dialog."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit, QMessageBox, QPushButton, QVBoxLayout

from app.config.user_settings import CREDENTIALS_FILE, install_google_credentials, read_config, save_api_key, save_model


class SetupDialog(QDialog):
    """Collect optional per-user settings without placing secrets in the project."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AI Gmail Organizer — Setup")
        self.setMinimumWidth(560)

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

        button_row = QHBoxLayout()
        save = QPushButton("Save")
        save.clicked.connect(self._save)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        button_row.addStretch()
        button_row.addWidget(cancel)
        button_row.addWidget(save)
        layout.addLayout(button_row)

    def _choose_credentials(self) -> None:
        source, _ = QFileDialog.getOpenFileName(self, "Select Google OAuth client JSON", "", "JSON files (*.json)")
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
