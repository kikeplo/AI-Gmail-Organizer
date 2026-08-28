"""Friendly application settings and guided Gmail connection."""

from __future__ import annotations

import webbrowser

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout,
)

from app.ai.provider import AIProvider
from app.config.user_settings import read_config, save_api_key, save_base_url, save_gmail_client_id, save_model, save_provider_name
from app.gmail.client import GmailClient


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


class _GoogleLogin(QThread):
    connected = Signal(str)
    failed = Signal(str)

    def run(self) -> None:
        try:
            client = GmailClient()
            client.connect()
            self.connected.emit("Google account connected")
        except Exception as exc:
            self.failed.emit(str(exc))


class GoogleSetupDialog(QDialog):
    """Plain-language, step-by-step Google OAuth setup for non-technical users."""

    ask_assistant = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Connect Gmail — One-time setup")
        self.setMinimumWidth(720)
        layout = QVBoxLayout(self)

        title = QLabel("Connect your Gmail account")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #F8FAFC;")
        layout.addWidget(title)
        intro = QLabel("Google requires a small one-time setup before a desktop app can securely sign you in. You only need to do this once on this computer.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #CBD5E1; font-size: 12px;")
        layout.addWidget(intro)

        steps = QLabel(
            "<b>Step 1 — Open Google Cloud</b><br>"
            "Click <b>Open Google Cloud</b> below and sign in with the Google account you want to use.<br><br>"
            "<b>Step 2 — Create/select a project</b><br>"
            "Create a project such as <b>AI Gmail Organizer</b>, or select an existing project.<br><br>"
            "<b>Step 3 — Enable Gmail</b><br>"
            "Go to <b>APIs & Services → Library</b>, search for <b>Gmail API</b>, and click <b>Enable</b>.<br><br>"
            "<b>Step 4 — Create a Desktop OAuth client</b><br>"
            "Go to <b>Google Auth Platform → Clients → Create client</b>. Choose <b>Desktop app</b> and create it.<br><br>"
            "<b>Step 5 — Copy the Client ID</b><br>"
            "Copy the <b>Client ID</b> (usually ending in <b>.apps.googleusercontent.com</b>) and paste it below. "
            "<b>Do not paste a Client Secret.</b>"
        )
        steps.setWordWrap(True)
        steps.setStyleSheet("color: #E2E8F0; font-size: 12px; line-height: 1.5;")
        layout.addWidget(steps)

        buttons = QHBoxLayout()
        cloud = QPushButton("Open Google Cloud")
        cloud.clicked.connect(lambda: webbrowser.open("https://console.cloud.google.com/"))
        auth = QPushButton("Open Google Auth Platform")
        auth.clicked.connect(lambda: webbrowser.open("https://console.cloud.google.com/auth/clients"))
        buttons.addWidget(cloud)
        buttons.addWidget(auth)
        layout.addLayout(buttons)

        self.client_id = QLineEdit(read_config().get("GMAIL_CLIENT_ID", ""))
        self.client_id.setPlaceholderText("Paste your Desktop app Client ID here")
        layout.addWidget(QLabel("Google Client ID"))
        layout.addWidget(self.client_id)

        help_row = QHBoxLayout()
        help_label = QLabel("Stuck on a step?")
        help_button = QPushButton("Ask the Assistant")
        help_button.clicked.connect(self._ask)
        help_row.addWidget(help_label)
        help_row.addWidget(help_button)
        help_row.addStretch()
        layout.addLayout(help_row)

        note = QLabel("🔒 Your Google password is entered only on Google's website. The Organizer never sees it. The Client ID is an app identifier, not your password.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #AAB4C4; font-size: 11px;")
        layout.addWidget(note)

        row = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        connect = QPushButton("Save & Sign in with Google")
        connect.clicked.connect(self._save_and_connect)
        row.addStretch()
        row.addWidget(cancel)
        row.addWidget(connect)
        layout.addLayout(row)
        self.setStyleSheet("""
            QDialog { background: #121620; color: #F1F5F9; }
            QLineEdit { color: #F7F8FA; background: #202738; border: 1px solid #3A4356; border-radius: 8px; padding: 10px; }
            QPushButton { color: #F7F8FA; background: #2A3346; border: 1px solid #46516A; border-radius: 8px; padding: 10px 14px; }
            QPushButton:hover { background: #35415B; }
        """)

    def _ask(self) -> None:
        self.ask_assistant.emit("Help me connect Gmail to AI Gmail Organizer. I am on the Google OAuth setup wizard and need help with the current step.")
        self.accept()

    def _save_and_connect(self) -> None:
        client_id = self.client_id.text().strip()
        if not client_id:
            QMessageBox.information(self, "Client ID needed", "Please paste the Desktop app Client ID first. It normally ends with .apps.googleusercontent.com.")
            return
        if not client_id.endswith(".apps.googleusercontent.com"):
            answer = QMessageBox.question(self, "Check the Client ID", "This doesn't look like a Google Desktop OAuth Client ID. It normally ends with .apps.googleusercontent.com. Save it anyway?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return
        try:
            save_gmail_client_id(client_id)
        except OSError as exc:
            QMessageBox.critical(self, "Could not save", str(exc))
            return
        self.accept()


class SetupDialog(QDialog):
    """Modern application settings with friendly provider and Gmail setup."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Gmail Organizer — Settings")
        self.setMinimumWidth(720)
        self._loader: _ModelLoader | None = None
        self._google_login: _GoogleLogin | None = None
        config = read_config()
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.provider = QLineEdit(config.get("AI_PROVIDER", ""))
        self.provider.setPlaceholderText("Optional — Gemini, Anthropic, Ollama, OpenRouter, etc.")
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
        self.model.setPlaceholderText("Automatic — select a model or leave blank")
        saved_model = config.get("OPENAI_MODEL", "")
        if saved_model:
            self.model.addItem(saved_model)
            self.model.setCurrentText(saved_model)
        refresh = QPushButton("Refresh models")
        refresh.clicked.connect(self._refresh_models)
        model_row.addWidget(self.model, 1)
        model_row.addWidget(refresh)
        form.addRow("Model", model_row)

        google_row = QHBoxLayout()
        self.google_status = QLineEdit()
        self.google_status.setReadOnly(True)
        self.google_status.setText("Ready to connect Gmail with Google")
        connect_google = QPushButton("Sign in with Google")
        connect_google.clicked.connect(self._connect_google)
        google_row.addWidget(self.google_status, 1)
        google_row.addWidget(connect_google)
        form.addRow("Gmail", google_row)
        layout.addLayout(form)

        note = QLabel("Tip: AI settings apply immediately after Save. Gmail sign-in opens your normal browser — your password never goes into this app.")
        note.setWordWrap(True)
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

    def _connect_google(self) -> None:
        config = read_config()
        if not config.get("GMAIL_CLIENT_ID", "").strip():
            wizard = GoogleSetupDialog(self)
            wizard.ask_assistant.connect(self._forward_assistant_help)
            if wizard.exec() != QDialog.Accepted:
                return
        self.google_status.setText("Opening Google sign-in in your browser…")
        self._google_login = _GoogleLogin()
        self._google_login.connected.connect(self._google_connected)
        self._google_login.failed.connect(self._google_failed)
        self._google_login.finished.connect(self._google_login.deleteLater)
        self._google_login.start()

    def _forward_assistant_help(self, prompt: str) -> None:
        parent = self.parent()
        if parent is not None and hasattr(parent, "_submit"):
            self.reject()
            parent._submit(prompt)

    def _google_connected(self, message: str) -> None:
        self.google_status.setText("✓ Google account connected")

    def _google_failed(self, message: str) -> None:
        self.google_status.setText("Sign-in needs attention — click again for help")
        QMessageBox.warning(self, "Google sign-in", message)

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
