"""Friendly application settings and guided Gmail connection."""

from __future__ import annotations

import webbrowser

from PySide6.QtCore import QByteArray, QThread, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QToolButton,
    QVBoxLayout, QWidget,
)

from app.ai.local_engine import LocalAIEngine, LocalAIError
from app.ai.provider import AIProvider
from app.config.user_settings import (
    read_config,
    save_api_key,
    save_backup_api_keys,
    save_base_url,
    save_gmail_client_id,
    save_local_ai,
    save_model,
    save_provider_name,
    save_routing_mode,
)
from app.gmail.client import GmailClient
from app.ui.help_dialog import HelpDialog


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


class _LocalInstaller(QThread):
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, engine: LocalAIEngine, model: str) -> None:
        super().__init__()
        self.engine = engine
        self.model = model

    def run(self) -> None:
        try:
            self.completed.emit(self.engine.install_model(self.model))
        except Exception as exc:
            self.failed.emit(str(exc))


class GoogleSetupDialog(QDialog):
    """Plain-language, step-by-step Google OAuth setup for non-technical users."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Connect Gmail — One-time setup")
        self.setMinimumWidth(720)
        layout = QVBoxLayout(self)
        title = QLabel("Connect your Gmail account")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #F8FAFC;")
        layout.addWidget(title)
        intro = QLabel("This one-time setup lets the app use Google's normal secure sign-in. You can ask for help at any point.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #CBD5E1; font-size: 12px;")
        layout.addWidget(intro)
        steps = QLabel(
            "<b>Step 1 — Open Google Cloud</b><br>Sign in with your Google account.<br><br>"
            "<b>Step 2 — Create or select a project</b><br>A project such as <b>AI Gmail Organizer</b> is fine.<br><br>"
            "<b>Step 3 — Enable Gmail API</b><br>Open <b>APIs & Services → Library</b>, search for <b>Gmail API</b>, then click <b>Enable</b>.<br><br>"
            "<b>Step 4 — Create a Desktop OAuth client</b><br>Open <b>Google Auth Platform → Clients → Create client</b>, choose <b>Desktop app</b>, then create it.<br><br>"
            "<b>Step 5 — Paste the Client ID</b><br>Copy the Client ID ending in <b>.apps.googleusercontent.com</b>. Do not paste a Client Secret."
        )
        steps.setWordWrap(True)
        steps.setStyleSheet("color: #E2E8F0; font-size: 12px;")
        layout.addWidget(steps)
        buttons = QHBoxLayout()
        cloud = QPushButton("Open Google Cloud")
        cloud.clicked.connect(lambda: webbrowser.open("https://console.cloud.google.com/"))
        auth = QPushButton("Open Google Auth Platform")
        auth.clicked.connect(lambda: webbrowser.open("https://console.cloud.google.com/auth/clients"))
        buttons.addWidget(cloud)
        buttons.addWidget(auth)
        layout.addLayout(buttons)
        layout.addWidget(QLabel("Google Client ID"))
        self.client_id = QLineEdit(read_config().get("GMAIL_CLIENT_ID", ""))
        self.client_id.setPlaceholderText("Paste your Desktop app Client ID here")
        layout.addWidget(self.client_id)
        help_row = QHBoxLayout()
        help_label = QLabel("Need help?")
        help_button = QPushButton("Ask the Assistant")
        help_button.clicked.connect(self._ask)
        help_row.addWidget(help_label)
        help_row.addWidget(help_button)
        help_row.addStretch()
        layout.addLayout(help_row)
        note = QLabel("Your Google password is entered only on Google's website. The Organizer never sees your password.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #AAB4C4; font-size: 11px;")
        layout.addWidget(note)
        row = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        connect = QPushButton("Save & continue")
        connect.clicked.connect(self._save)
        row.addStretch()
        row.addWidget(cancel)
        row.addWidget(connect)
        layout.addLayout(row)
        self.setStyleSheet(
            """QDialog { background: #121620; color: #F1F5F9; }
            QLineEdit { color: #F7F8FA; background: #202738; border: 1px solid #3A4356; border-radius: 8px; padding: 10px; }
            QPushButton { color: #F7F8FA; background: #2A3346; border: 1px solid #46516A; border-radius: 8px; padding: 10px 14px; }
            QPushButton:hover { background: #35415B; }"""
        )

    def _ask(self) -> None:
        try:
            HelpDialog(self).exec()
        except Exception as exc:
            QMessageBox.critical(self, "Help could not be opened", f"The help assistant could not be opened.\n\n{exc}")

    def _save(self) -> None:
        client_id = self.client_id.text().strip()
        if not client_id:
            QMessageBox.information(
                self,
                "Client ID needed",
                "Please paste the Desktop app Client ID first. It normally ends with .apps.googleusercontent.com.",
            )
            return
        if not client_id.endswith(".apps.googleusercontent.com"):
            answer = QMessageBox.question(
                self,
                "Check the Client ID",
                "This doesn't look like a Google Desktop OAuth Client ID. It normally ends with .apps.googleusercontent.com. Save it anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
        try:
            save_gmail_client_id(client_id)
        except OSError as exc:
            QMessageBox.critical(self, "Could not save", str(exc))
            return
        self.accept()


class SetupDialog(QDialog):
    """Responsive application settings with cloud failover, local AI, and Gmail setup."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Gmail Organizer — Settings")
        self.setMinimumSize(620, 480)
        self._loader: _ModelLoader | None = None
        self._google_login: _GoogleLogin | None = None
        self._local_installer: _LocalInstaller | None = None

        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            width = min(820, max(620, available.width() - 80))
            height = min(760, max(480, available.height() - 80))
            self.resize(width, height)
        else:
            self.resize(820, 720)

        config = read_config()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Keep the action bar outside the scroll area so Save/Cancel are always visible.
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(8, 4, 8, 8)
        content_layout.setSpacing(10)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setVerticalSpacing(9)
        form.setHorizontalSpacing(12)

        self.provider = QLineEdit(config.get("AI_PROVIDER", ""))
        self.provider.setPlaceholderText("Optional — Gemini, Anthropic, OpenAI, OpenRouter, etc.")
        form.addRow("Cloud AI provider", self.provider)

        self.api_key = QLineEdit(config.get("OPENAI_API_KEY", ""))
        self.api_key.setEchoMode(QLineEdit.Password)
        self.api_key.setPlaceholderText("Primary API key")
        primary_row = QHBoxLayout()
        primary_row.setContentsMargins(0, 0, 0, 0)
        primary_row.setSpacing(6)
        primary_row.addWidget(self.api_key, 1)
        primary_row.addWidget(self._make_eye_button(self.api_key))
        form.addRow("Primary API key", primary_row)

        backup_text = config.get("OPENAI_API_KEYS", "")
        backup_values = [item.strip() for chunk in backup_text.splitlines() for item in chunk.split(",") if item.strip()]
        for index in range(1, 6):
            legacy = config.get("OPENAI_API_KEY_BACKUP" if index == 1 else f"OPENAI_API_KEY_BACKUP_{index}", "").strip()
            if legacy and legacy not in backup_values:
                backup_values.append(legacy)
        self.backup_keys: list[QLineEdit] = []
        backup_container = QVBoxLayout()
        backup_container.setContentsMargins(0, 0, 0, 0)
        backup_container.setSpacing(6)
        self.show_backups = QPushButton("Show backup API keys")
        self.show_backups.setCheckable(True)
        self.show_backups.setObjectName("showBackupsButton")
        self.show_backups.toggled.connect(self._toggle_backup_visibility)
        backup_container.addWidget(self.show_backups)
        self.backup_fields_container = QVBoxLayout()
        self.backup_fields_container.setContentsMargins(0, 0, 0, 0)
        self.backup_fields_container.setSpacing(6)
        for index in range(5):
            field = QLineEdit(backup_values[index] if index < len(backup_values) else "")
            field.setEchoMode(QLineEdit.Password)
            field.setPlaceholderText(f"Backup API key {index + 1} — optional")
            field.setClearButtonEnabled(True)
            self.backup_keys.append(field)
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)
            row.addWidget(field, 1)
            row.addWidget(self._make_eye_button(field))
            self.backup_fields_container.addLayout(row)
        backup_hint = QLabel("Backup keys are rotated automatically when the primary key is unavailable, rate-limited, or over quota. Keys stay in local app settings.")
        backup_hint.setWordWrap(True)
        backup_hint.setObjectName("backupHint")
        self.backup_fields_container.addWidget(backup_hint)
        backup_container.addLayout(self.backup_fields_container)
        self._set_backup_fields_visible(False)
        form.addRow("Backup API keys", backup_container)

        self.base_url = QLineEdit(config.get("OPENAI_BASE_URL", ""))
        self.base_url.setPlaceholderText("API endpoint/base URL")
        form.addRow("Cloud API base URL", self.base_url)

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
        form.addRow("Cloud model", model_row)

        self.local_enabled = QCheckBox("Use Local AI when available")
        self.local_enabled.setChecked(config.get("LOCAL_AI_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"})
        self.local_enabled.toggled.connect(self._toggle_local_controls)
        form.addRow("Local AI", self.local_enabled)

        local_model_row = QHBoxLayout()
        self.local_model = QLineEdit(config.get("LOCAL_AI_MODEL", LocalAIEngine.DEFAULT_MODEL) or LocalAIEngine.DEFAULT_MODEL)
        self.local_model.setPlaceholderText("qwen3:4b")
        local_model_row.addWidget(self.local_model, 1)
        self.local_check = QPushButton("Check local AI")
        self.local_check.clicked.connect(self._check_local_ai)
        local_model_row.addWidget(self.local_check)
        self.local_install = QPushButton("Install model")
        self.local_install.clicked.connect(self._install_local_model)
        local_model_row.addWidget(self.local_install)
        form.addRow("Local model", local_model_row)

        self.local_base_url = QLineEdit(config.get("LOCAL_AI_BASE_URL", LocalAIEngine.DEFAULT_BASE_URL) or LocalAIEngine.DEFAULT_BASE_URL)
        self.local_base_url.setPlaceholderText(LocalAIEngine.DEFAULT_BASE_URL)
        form.addRow("Local AI URL", self.local_base_url)

        self.local_status = QLabel("Local AI status: not checked")
        self.local_status.setWordWrap(True)
        self.local_status.setObjectName("localStatus")
        form.addRow("Status", self.local_status)

        routing_value = config.get("AI_ROUTING_MODE", "local-first") or "local-first"
        self.routing = QComboBox()
        self.routing.addItems(["local-first", "cloud-first", "balanced", "local-only"])
        self.routing.setCurrentText(routing_value if routing_value in {"local-first", "cloud-first", "balanced", "local-only"} else "local-first")
        form.addRow("AI routing", self.routing)
        routing_hint = QLabel("Local-first keeps normal AI work on your PC. When Local AI is missing, stopped, or fails, the app automatically uses the configured cloud provider. Local-only never sends requests to cloud AI.")
        routing_hint.setWordWrap(True)
        routing_hint.setObjectName("routingHint")
        form.addRow("", routing_hint)

        google_row = QHBoxLayout()
        self.google_status = QLineEdit()
        self.google_status.setReadOnly(True)
        self.google_status.setText("Ready to connect Gmail with Google")
        connect_google = QPushButton("Sign in with Google")
        connect_google.clicked.connect(self._connect_google)
        google_row.addWidget(self.google_status, 1)
        google_row.addWidget(connect_google)
        form.addRow("Gmail", google_row)

        content_layout.addLayout(form)

        self.capability_box = QLabel("Capabilities\nNot checked yet — select a cloud model or leave it on Automatic, then click Check capabilities.")
        self.capability_box.setWordWrap(True)
        self.capability_box.setObjectName("capabilityBox")
        content_layout.addWidget(self.capability_box)

        capability_button = QPushButton("Check cloud capabilities")
        capability_button.clicked.connect(self._check_capabilities)
        content_layout.addWidget(capability_button)

        note = QLabel("Settings apply immediately after Save. The local model is optional; cloud AI remains the automatic fallback unless you select Local-only. API keys are stored locally and displayed masked.")
        note.setWordWrap(True)
        note.setObjectName("settingsNote")
        content_layout.addWidget(note)
        content_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content_widget)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setObjectName("settingsScroll")
        layout.addWidget(scroll, 1)

        button_row = QHBoxLayout()
        help_button = QPushButton("Help")
        help_button.clicked.connect(self._open_help)
        save = QPushButton("Save")
        save.clicked.connect(self._save)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        button_row.addWidget(help_button)
        button_row.addStretch()
        button_row.addWidget(cancel)
        button_row.addWidget(save)
        layout.addLayout(button_row)

        self.setStyleSheet(
            """
            QDialog { background: #121620; color: #F1F5F9; }
            QLabel { color: #E3E8F0; }
            QLineEdit, QComboBox { color: #F7F8FA; background: #202738; border: 1px solid #3A4356; border-radius: 8px; padding: 9px; }
            QComboBox QAbstractItemView { color: #F7F8FA; background: #202738; selection-background-color: #35415B; }
            QCheckBox { color: #F7F8FA; spacing: 8px; }
            QPushButton, QToolButton { color: #F7F8FA; background: #2A3346; border: 1px solid #46516A; border-radius: 8px; padding: 9px 14px; }
            QPushButton:hover, QToolButton:hover { background: #35415B; }
            QPushButton#showBackupsButton { text-align: left; background: transparent; border: none; color: #B7C3D6; padding: 5px 2px; }
            QPushButton#showBackupsButton:hover { color: #FFFFFF; background: transparent; }
            QToolButton#apiKeyEye { padding: 6px; min-width: 38px; max-width: 38px; min-height: 34px; max-height: 34px; }
            #settingsNote, #backupHint, #routingHint { color: #AAB4C4; background: transparent; border: none; }
            #localStatus { color: #DCE5F3; background: #1A2231; border: 1px solid #354057; border-radius: 9px; padding: 9px; }
            #capabilityBox { color: #EAF0F8; background: #1A2231; border: 1px solid #354057; border-radius: 10px; padding: 12px; }
            QScrollArea#settingsScroll { background: transparent; border: none; }
            QScrollBar:vertical { width: 8px; background: transparent; margin: 2px 0 2px 0; }
            QScrollBar::handle:vertical { background: #46516A; border-radius: 4px; min-height: 30px; }
            QScrollBar::handle:vertical:hover { background: #5B6882; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            """
        )
        self._toggle_local_controls(self.local_enabled.isChecked())
        self._check_local_ai(show_message=False)

    @staticmethod
    def _eye_icon() -> QIcon:
        svg = b'''<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2.2 12s3.4-6 9.8-6 9.8 6 9.8 6-3.4 6-9.8 6-9.8-6-9.8-6Z"/><circle cx="12" cy="12" r="2.6"/></svg>'''
        pixmap = QPixmap()
        pixmap.loadFromData(QByteArray(svg), "SVG")
        return QIcon(pixmap)

    @classmethod
    def _make_eye_button(cls, field: QLineEdit) -> QToolButton:
        button = QToolButton()
        button.setObjectName("apiKeyEye")
        button.setCheckable(True)
        button.setIcon(cls._eye_icon())
        button.setToolTip("Show API key")
        button.toggled.connect(lambda visible, target=field, eye=button: cls._toggle_key_visibility(target, eye, visible))
        return button

    @staticmethod
    def _toggle_key_visibility(field: QLineEdit, button: QToolButton, visible: bool) -> None:
        field.setEchoMode(QLineEdit.Normal if visible else QLineEdit.Password)
        button.setToolTip("Hide API key" if visible else "Show API key")

    def _set_backup_fields_visible(self, visible: bool) -> None:
        for index in range(self.backup_fields_container.count()):
            item = self.backup_fields_container.itemAt(index)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.setVisible(visible)
            else:
                self._set_layout_item_visible(item, visible)

    @staticmethod
    def _set_layout_item_visible(item, visible: bool) -> None:
        layout = item.layout()
        if layout is None:
            return
        for index in range(layout.count()):
            child = layout.itemAt(index)
            if child.widget() is not None:
                child.widget().setVisible(visible)
            else:
                SetupDialog._set_layout_item_visible(child, visible)

    def _toggle_backup_visibility(self, visible: bool) -> None:
        self._set_backup_fields_visible(visible)
        self.show_backups.setText("Hide backup API keys" if visible else "Show backup API keys")

    def _toggle_local_controls(self, enabled: bool) -> None:
        self.local_model.setEnabled(enabled)
        self.local_base_url.setEnabled(enabled)
        self.local_check.setEnabled(enabled)
        self.local_install.setEnabled(enabled)

    def _local_engine_from_form(self) -> LocalAIEngine:
        engine = LocalAIEngine()
        engine.enabled = self.local_enabled.isChecked()
        engine.base_url = self.local_base_url.text().strip().rstrip("/") or LocalAIEngine.DEFAULT_BASE_URL
        engine.model = self.local_model.text().strip() or LocalAIEngine.DEFAULT_MODEL
        return engine

    def _check_local_ai(self, show_message: bool = True) -> None:
        if not self.local_enabled.isChecked():
            self.local_status.setText("Local AI status: disabled. Cloud AI will be used.")
            return
        try:
            status = self._local_engine_from_form().status()
            if status["available"]:
                self.local_status.setText(
                    f"Local AI: ready\nModel: {status['model']}\nRuntime: Ollama-compatible endpoint detected."
                )
            elif status.get("ollama_installed"):
                self.local_status.setText(
                    f"Local AI: Ollama is installed, but the model/runtime is not ready.\n\n{status['reason']}"
                )
            else:
                self.local_status.setText(
                    "Local AI: not available. Install Ollama and then install the selected model. "
                    "Cloud AI will be used automatically meanwhile."
                )
        except Exception as exc:
            self.local_status.setText(f"Local AI: unavailable — {exc}\nCloud AI will be used automatically.")
            if show_message:
                QMessageBox.information(self, "Local AI unavailable", str(exc))

    def _install_local_model(self) -> None:
        engine = self._local_engine_from_form()
        if not engine.ollama_executable:
            QMessageBox.information(
                self,
                "Ollama required",
                "Ollama is not installed. Install Ollama first, then use Install model here. Cloud AI will continue to work automatically.",
            )
            return
        if self._local_installer is not None and self._local_installer.isRunning():
            return
        self.local_install.setEnabled(False)
        self.local_check.setEnabled(False)
        self.local_status.setText(f"Installing {engine.model} with Ollama…")
        self._local_installer = _LocalInstaller(engine, engine.model)
        self._local_installer.completed.connect(self._local_install_done)
        self._local_installer.failed.connect(self._local_install_failed)
        self._local_installer.finished.connect(self._local_installer.deleteLater)
        self._local_installer.start()

    def _local_install_done(self, message: str) -> None:
        self.local_install.setEnabled(self.local_enabled.isChecked())
        self.local_check.setEnabled(self.local_enabled.isChecked())
        self._check_local_ai(show_message=False)
        QMessageBox.information(self, "Local AI ready", f"The local model is installed.\n\n{message}")

    def _local_install_failed(self, message: str) -> None:
        self.local_install.setEnabled(self.local_enabled.isChecked())
        self.local_check.setEnabled(self.local_enabled.isChecked())
        self._check_local_ai(show_message=False)
        QMessageBox.warning(self, "Local AI setup", message)

    def _provider_for_form(self) -> AIProvider:
        provider = AIProvider()
        provider.provider = self.provider.text().strip()
        provider.api_key = self.api_key.text().strip()
        provider.api_keys = [provider.api_key] if provider.api_key else []
        for field in self.backup_keys:
            key = field.text().strip()
            if key and key not in provider.api_keys:
                provider.api_keys.append(key)
        provider.base_url = self.base_url.text().strip()
        provider.model = self.model.currentText().strip()
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
        self._check_capabilities()

    def _models_failed(self, message: str) -> None:
        self.model.setEnabled(True)
        QMessageBox.warning(self, "Could not load models", message)

    def _check_capabilities(self) -> None:
        try:
            provider = self._provider_for_form()
            model = provider.model or None
            caps = provider.capabilities(model)
            labels = caps.labels()
            self.capability_box.setText(
                "Capabilities\n"
                + ("\n".join("✓ " + label for label in labels) if labels else "No cloud capabilities detected.")
                + ("\n✗ Vision" if not caps.vision else "")
            )
        except Exception as exc:
            self.capability_box.setText(f"Capabilities\nCould not determine capabilities: {exc}")

    def _connect_google(self) -> None:
        config = read_config()
        if not config.get("GMAIL_CLIENT_ID", "").strip():
            wizard = GoogleSetupDialog(self)
            if wizard.exec() != QDialog.Accepted:
                return
        self.google_status.setText("Opening Google sign-in in your browser…")
        self._google_login = _GoogleLogin()
        self._google_login.connected.connect(self._google_connected)
        self._google_login.failed.connect(self._google_failed)
        self._google_login.finished.connect(self._google_login.deleteLater)
        self._google_login.start()

    def _google_connected(self, message: str) -> None:
        self.google_status.setText("✓ Google account connected")

    def _google_failed(self, message: str) -> None:
        self.google_status.setText("Sign-in needs attention — click Help for guidance")
        QMessageBox.warning(self, "Google sign-in", message)

    def _open_help(self) -> None:
        try:
            HelpDialog(self).exec()
        except Exception as exc:
            QMessageBox.critical(self, "Help could not be opened", f"The help window could not be opened.\n\n{exc}")

    def _save(self) -> None:
        try:
            save_provider_name(self.provider.text())
            save_api_key(self.api_key.text())
            save_backup_api_keys([field.text() for field in self.backup_keys])
            save_base_url(self.base_url.text())
            save_model(self.model.currentText().strip())
            save_local_ai(
                self.local_enabled.isChecked(),
                self.local_base_url.text().strip() or LocalAIEngine.DEFAULT_BASE_URL,
                self.local_model.text().strip() or LocalAIEngine.DEFAULT_MODEL,
            )
            save_routing_mode(self.routing.currentText())
        except OSError as exc:
            QMessageBox.critical(self, "Could not save settings", str(exc))
            return
        self.accept()
