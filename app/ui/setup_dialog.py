"""First-run and application settings dialog."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout,
)

from app.ai.provider import AIProvider, AIProviderError
from app.config.user_settings import (
    CREDENTIALS_FILE, ENV_FILE, install_google_credentials, read_config,
    save_api_key, save_base_url, save_model, save_provider_name,
)


class _ModelLoader(QThread):
    models_loaded = Signal(list)
    load_failed = Signal(str)

    def __init__(self, provider: AIProvider) -> None:
        super().__init__()
        self.provider = provider

    def run(self) -> None:
        try:
            self.models_loaded.emit(self.provider.list_models())
        except Exception as exc:
            self.load_failed.emit(str(exc))


class SetupDialog(QDialog):
    """Collect and edit per-user application settings."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Gmail Organizer — Settings")
        self.setMinimumWidth(700)
        self._loader: _ModelLoader | None = None
        config = read_config()
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.provider = QLineEdit(config.get("AI_PROVIDER", ""))
        self.provider.setPlaceholderText("Optional — e.g. Gemini, Anthropic, Ollama, OpenRouter")
        form.addRow("AI provider", self.provider)

        self.api_key = QLineEdit(config.get("OPENAI_API_KEY", ""))
        self.api_key.setEchoMode(QLineEdit.Password)
        self.api_key.setPlaceholderText("Optional for keyless/local providers")
        form.addRow("API key", self.api_key)

        self.base_url = QLineEdit(config.get("OPENAI_BASE_URL", ""))
        self.base_url.setPlaceholderText("API endpoint/base URL")
        form.addRow("API base URL", self.base_url)

        model_row = QHBoxLayout()
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.setInsertPolicy(QComboBox.NoInsert)
        saved_model = config.get("OPENAI_MODEL", "")
        self.model.setPlaceholderText("Automatic — choose a model or leave blank")
        if saved_model:
            self.model.addItem(saved_model)
            self.model.setCurrentText(saved_model)
        refresh = QPushButton("Refresh models")
        refresh.clicked.connect(self._refresh_models)
        model_row.addWidget(self.model, 1)
        model_row.addWidget(refresh)
        form.addRow("Model", model_row)

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

        note = QLineEdit("Enter your provider/key/base URL, then Refresh models. Leave Model blank to let the app choose automatically.")
        note.setReadOnly(True)
        note.setObjectName("settingsNote")
        layout.addWidget(note)

        button_row = QHBoxLayout()
        save = QPushButton("Save")
        save.clicked.connect(self._save)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        button_row.addStretch()
        button_row.addWidget(cancel)
        button_row.addWidget(save)
        layout.addLayout(button_row)

        self.setStyleSheet("""
            QDialog { background: #121620; color: #F1F5F9; }
            QLabel { color: #E3E8F0; }
            QLineEdit, QComboBox { color: #F7F8FA; background: #202738; border: 1px solid #3A4356; border-radius: 8px; padding: 9px; }
            QLineEdit:focus, QComboBox:focus { border-color: #6D86F7; }
            QComboBox QAbstractItemView { color: #F7F8FA; background: #202738; selection-background-color: #35415B; }
            QPushButton { color: #F7F8FA; background: #2A3346; border: 1px solid #46516A; border-radius: 8px; padding: 9px 14px; }
            QPushButton:hover { background: #35415B; }
            #settingsNote { color: #AAB4C4; background: transparent; border: none; }
        """)

    def _provider_for_form(self) -> AIProvider:
        provider = AIProvider()
        provider.provider = self.provider.text().strip()
        provider.api_key = self.api_key.text().strip()
        provider.base_url = self.base_url.text().strip()
        return provider

    def _refresh_models(self) -> None:
        if self._loader is not None and self._loader.isRunning():
            return
        try:
            provider = self._provider_for_form()
            if not provider.configured and not provider.provider:
                QMessageBox.information(self, "Provider required", "Enter an API key or base URL first.")
                return
            self.model.setEnabled(False)
            self._loader = _ModelLoader(provider)
            self._loader.models_loaded.connect(self._models_loaded)
            self._loader.load_failed.connect(self._models_failed)
            self._loader.finished.connect(self._loader.deleteLater)
            self._loader.start()
        except Exception as exc:
            QMessageBox.warning(self, "Could not load models", str(exc))

    def _models_loaded(self, models: list) -> None:
        current = self.model.currentText().strip()
        self.model.clear()
        self.model.addItem("")
        for model in models:
            self.model.addItem(str(model))
        if current:
            index = self.model.findText(current)
            if index >= 0:
                self.model.setCurrentIndex(index)
            else:
                self.model.setCurrentText(current)
        self.model.setEnabled(True)

    def _models_failed(self, message: str) -> None:
        self.model.setEnabled(True)
        QMessageBox.warning(self, "Could not load models", message)

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
            save_provider_name(self.provider.text())
            save_api_key(self.api_key.text())
            save_base_url(self.base_url.text())
            save_model(self.model.currentText().strip())
        except OSError as exc:
            QMessageBox.critical(self, "Could not save settings", str(exc))
            return
        self.accept()
