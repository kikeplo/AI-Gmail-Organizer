"""Application settings and guided Gmail connection."""

from __future__ import annotations

import webbrowser

from PySide6.QtCore import QByteArray, QThread, Signal, Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap, QGuiApplication
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QProgressBar, QScrollArea,
    QToolButton, QVBoxLayout, QWidget,
)

from app.ai.local_engine import LocalAIEngine
from app.ai.provider import AIProvider
from app.config.user_settings import (
    read_config, save_api_key, save_backup_api_keys, save_base_url,
    save_gmail_client_id, save_local_ai, save_model, save_provider_name,
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
    progress = Signal(str, int, int)

    def __init__(self, engine: LocalAIEngine, model: str) -> None:
        super().__init__()
        self.engine = engine
        self.model = model

    def run(self) -> None:
        try:
            self.completed.emit(self.engine.install_model(self.model, progress_callback=self._progress))
        except Exception as exc:
            self.failed.emit(str(exc))

    def _progress(self, status: str, completed: int, total: int) -> None:
        self.progress.emit(status, completed, total)


class GoogleSetupDialog(QDialog):
    """Plain-language, step-by-step Google OAuth setup."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Connect Gmail — One-time setup")
        self.setMinimumWidth(720)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Connect your Gmail account"))
        intro = QLabel("This one-time setup lets the app use Google's normal secure sign-in. You can ask for help at any point.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        steps = QLabel(
            "<b>Step 1 — Open Google Cloud</b><br>Sign in with your Google account.<br><br>"
            "<b>Step 2 — Create or select a project</b><br>A project such as <b>AI Gmail Organizer</b> is fine.<br><br>"
            "<b>Step 3 — Enable Gmail API</b><br>Open <b>APIs & Services → Library</b>, search for <b>Gmail API</b>, then click <b>Enable</b>.<br><br>"
            "<b>Step 4 — Create a Desktop OAuth client</b><br>Open <b>Google Auth Platform → Clients → Create client</b>, choose <b>Desktop app</b>, then create it.<br><br>"
            "<b>Step 5 — Paste the Client ID</b><br>Copy the Client ID ending in <b>.apps.googleusercontent.com</b>. Do not paste a Client Secret."
        )
        steps.setWordWrap(True)
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
        row = QHBoxLayout()
        cancel = QPushButton("Cancel"); cancel.clicked.connect(self.reject)
        connect = QPushButton("Save & continue"); connect.clicked.connect(self._save)
        row.addStretch(); row.addWidget(cancel); row.addWidget(connect)
        layout.addLayout(row)
        self.setStyleSheet("""
        QDialog, QWidget { background:#121620; color:#F1F5F9; }
        QLabel { color:#E3E8F0; }
        QLineEdit { color:#F7F8FA; background:#202738; border:1px solid #3A4356; border-radius:8px; padding:10px; }
        QPushButton { color:#F7F8FA; background:#2A3346; border:1px solid #46516A; border-radius:8px; padding:10px 14px; }
        """)

    def _save(self) -> None:
        client_id = self.client_id.text().strip()
        if not client_id:
            QMessageBox.information(self, "Client ID needed", "Please paste the Desktop app Client ID first.")
            return
        try:
            save_gmail_client_id(client_id)
        except OSError as exc:
            QMessageBox.critical(self, "Could not save", str(exc))
            return
        self.accept()


class SetupDialog(QDialog):
    """Responsive settings dialog with a fixed viewport and scrollable content."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Gmail Organizer — Settings")
        self._loader: _ModelLoader | None = None
        self._google_login: _GoogleLogin | None = None
        self._local_installer: _LocalInstaller | None = None

        screen = self.screen() or QGuiApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        if available:
            width = min(820, max(620, available.width() - 80))
            height = min(700, max(480, available.height() - 80))
        else:
            width, height = 820, 700
        self.setMinimumSize(620, 480)
        self.setMaximumSize(width, height)
        self.resize(width, height)

        config = read_config()
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        content = QWidget()
        content.setObjectName("settingsContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 6, 8, 10)
        content_layout.setSpacing(10)
        form = QFormLayout()
        form.setVerticalSpacing(9)
        form.setHorizontalSpacing(12)

        self.provider = QLineEdit(config.get("AI_PROVIDER", ""))
        self.provider.setPlaceholderText("Optional — Gemini, Anthropic, OpenAI, OpenRouter, etc.")
        form.addRow("Cloud AI provider", self.provider)

        self.api_key = QLineEdit(config.get("OPENAI_API_KEY", ""))
        self.api_key.setEchoMode(QLineEdit.Password)
        self.api_key.setPlaceholderText("Primary API key")
        primary = QHBoxLayout(); primary.setContentsMargins(0, 0, 0, 0); primary.addWidget(self.api_key, 1); primary.addWidget(self._make_eye_button(self.api_key))
        form.addRow("Primary API key", primary)

        backup_text = config.get("OPENAI_API_KEYS", "")
        backup_values = [x.strip() for chunk in backup_text.splitlines() for x in chunk.split(",") if x.strip()]
        for index in range(1, 6):
            legacy = config.get("OPENAI_API_KEY_BACKUP" if index == 1 else f"OPENAI_API_KEY_BACKUP_{index}", "").strip()
            if legacy and legacy not in backup_values: backup_values.append(legacy)
        self.backup_keys: list[QLineEdit] = []
        self.backup_rows: list[QHBoxLayout] = []
        backup_container = QVBoxLayout(); backup_container.setContentsMargins(0, 0, 0, 0); backup_container.setSpacing(6)
        self.show_backups = QPushButton("Show backup API keys")
        self.show_backups.setCheckable(True)
        self.show_backups.setObjectName("showBackupsButton")
        self.show_backups.toggled.connect(self._toggle_backup_visibility)
        backup_container.addWidget(self.show_backups)
        self.backup_fields_container = QWidget(); self.backup_fields_container.setObjectName("backupFieldsContainer"); backup_fields_layout = QVBoxLayout(self.backup_fields_container); backup_fields_layout.setContentsMargins(0, 0, 0, 0); backup_fields_layout.setSpacing(6)
        for index in range(5):
            field = QLineEdit(backup_values[index] if index < len(backup_values) else "")
            field.setEchoMode(QLineEdit.Password); field.setClearButtonEnabled(True); field.setPlaceholderText(f"Backup API key {index + 1} — optional")
            self.backup_keys.append(field)
            row = QHBoxLayout(); row.setContentsMargins(0, 0, 0, 0); row.addWidget(field, 1); row.addWidget(self._make_eye_button(field)); backup_fields_layout.addLayout(row); self.backup_rows.append(row)
        hint = QLabel("Backup keys are rotated automatically when the primary key is unavailable, rate-limited, or over quota. Keys stay in local app settings."); hint.setWordWrap(True); hint.setObjectName("backupHint"); backup_fields_layout.addWidget(hint)
        backup_container.addWidget(self.backup_fields_container)
        self.backup_fields_container.setVisible(False)
        form.addRow("Backup API keys", backup_container)

        self.base_url = QLineEdit(config.get("OPENAI_BASE_URL", "")); self.base_url.setPlaceholderText("API endpoint/base URL"); form.addRow("Cloud API base URL", self.base_url)
        model_row = QHBoxLayout(); self.model = QComboBox(); self.model.setEditable(True); self.model.setInsertPolicy(QComboBox.NoInsert); self.model.setPlaceholderText("Automatic — select a model or leave blank"); saved_model = config.get("OPENAI_MODEL", "")
        if saved_model: self.model.addItem(saved_model); self.model.setCurrentText(saved_model)
        refresh = QPushButton("Refresh models"); refresh.clicked.connect(self._refresh_models); model_row.addWidget(self.model, 1); model_row.addWidget(refresh); form.addRow("Cloud model", model_row)

        self.local_enabled = QCheckBox("Use Local AI when available"); self.local_enabled.setChecked(config.get("LOCAL_AI_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}); self.local_enabled.toggled.connect(self._toggle_local_controls); form.addRow("Local AI", self.local_enabled)
        local_row = QHBoxLayout(); self.local_model = QLineEdit(config.get("LOCAL_AI_MODEL", LocalAIEngine.DEFAULT_MODEL) or LocalAIEngine.DEFAULT_MODEL); self.local_model.setPlaceholderText("qwen3:1.7b"); self.local_check = QPushButton("Check local AI"); self.local_check.clicked.connect(self._check_local_ai); self.local_install = QPushButton("Install model"); self.local_install.clicked.connect(self._install_local_model); local_row.addWidget(self.local_model, 1); local_row.addWidget(self.local_check); local_row.addWidget(self.local_install); form.addRow("Local model", local_row)
        self.local_base_url = QLineEdit(config.get("LOCAL_AI_BASE_URL", LocalAIEngine.DEFAULT_BASE_URL) or LocalAIEngine.DEFAULT_BASE_URL); self.local_base_url.setPlaceholderText(LocalAIEngine.DEFAULT_BASE_URL); form.addRow("Local AI URL", self.local_base_url)
        self.local_status = QLabel("Local AI status: checking…"); self.local_status.setWordWrap(True); self.local_status.setObjectName("localStatus"); form.addRow("Status", self.local_status)
        self.local_install_status = QLabel("Install status: ready"); self.local_install_status.setWordWrap(True); self.local_install_status.setObjectName("localInstallStatus"); form.addRow("Model install", self.local_install_status)
        self.local_progress = QProgressBar(); self.local_progress.setRange(0, 100); self.local_progress.setValue(0); self.local_progress.setTextVisible(True); self.local_progress.setObjectName("localProgress"); self.local_progress.setVisible(False); form.addRow("Download", self.local_progress)
        routing_value = config.get("AI_ROUTING_MODE", "local-first") or "local-first"; self.routing = QComboBox(); self.routing.addItems(["local-first", "cloud-first", "balanced", "local-only"]); self.routing.setCurrentText(routing_value if routing_value in {"local-first", "cloud-first", "balanced", "local-only"} else "local-first"); form.addRow("AI routing", self.routing)
        routing_hint = QLabel("Local-first keeps normal AI work on your PC. When Local AI is missing, stopped, or fails, the app automatically uses the configured cloud provider. Local-only never sends requests to cloud AI."); routing_hint.setWordWrap(True); routing_hint.setObjectName("routingHint"); form.addRow("", routing_hint)

        google_row = QHBoxLayout(); self.google_status = QLineEdit("Ready to connect Gmail with Google"); self.google_status.setReadOnly(True); connect_google = QPushButton("Sign in with Google"); connect_google.clicked.connect(self._connect_google); google_row.addWidget(self.google_status, 1); google_row.addWidget(connect_google); form.addRow("Gmail", google_row)
        content_layout.addLayout(form)
        self.capability_box = QLabel("Capabilities\nNot checked yet — select a cloud model or leave it on Automatic, then click Check capabilities."); self.capability_box.setWordWrap(True); self.capability_box.setObjectName("capabilityBox"); content_layout.addWidget(self.capability_box)
        capability = QPushButton("Check cloud capabilities"); capability.clicked.connect(self._check_capabilities); content_layout.addWidget(capability)
        note = QLabel("Settings apply after Save. Local AI is optional; cloud AI remains the automatic fallback unless you select Local-only. API keys are stored locally and displayed masked."); note.setWordWrap(True); note.setObjectName("settingsNote"); content_layout.addWidget(note); content_layout.addStretch()

        scroll = QScrollArea(); scroll.setObjectName("settingsScroll"); scroll.setWidgetResizable(True); scroll.setFrameShape(QScrollArea.NoFrame); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded); scroll.setWidget(content)
        scroll.viewport().setObjectName("settingsViewport")
        root.addWidget(scroll, 1)
        buttons = QHBoxLayout(); help_button = QPushButton("Help"); help_button.clicked.connect(self._open_help); cancel = QPushButton("Cancel"); cancel.clicked.connect(self.reject); save = QPushButton("Save"); save.clicked.connect(self._save); buttons.addWidget(help_button); buttons.addStretch(); buttons.addWidget(cancel); buttons.addWidget(save); root.addLayout(buttons)

        self.setStyleSheet("""
        QDialog#SetupDialog, QWidget#settingsContent, QScrollArea#settingsScroll, QWidget#settingsViewport {
            background: #121620;
            color: #F1F5F9;
        }
        QLabel { color: #E3E8F0; }
        QLineEdit, QComboBox {
            color: #F7F8FA;
            background: #202738;
            border: 1px solid #3A4356;
            border-radius: 8px;
            padding: 9px;
        }
        QComboBox QAbstractItemView {
            color: #F7F8FA;
            background: #202738;
            selection-background-color: #35415B;
            selection-color: #FFFFFF;
        }
        QCheckBox { color: #F7F8FA; spacing: 8px; }
        QProgressBar {
            color: #F7F8FA;
            background: #202738;
            border: 1px solid #3A4356;
            border-radius: 7px;
            text-align: center;
            min-height: 18px;
        }
        QProgressBar::chunk { background: #4F6B95; border-radius: 6px; }
        QPushButton, QToolButton {
            color: #F7F8FA;
            background: #2A3346;
            border: 1px solid #46516A;
            border-radius: 8px;
            padding: 9px 14px;
        }
        QPushButton:hover, QToolButton:hover { background: #35415B; }
        QPushButton#showBackupsButton {
            text-align: left;
            background: transparent;
            border: none;
            color: #B7C3D6;
            padding: 5px 2px;
        }
        QPushButton#showBackupsButton:hover {
            color: #FFFFFF;
            background: transparent;
        }
        QToolButton#apiKeyEye {
            padding: 6px;
            min-width: 38px;
            max-width: 38px;
            min-height: 34px;
            max-height: 34px;
        }
        #settingsNote, #backupHint, #routingHint {
            color: #AAB4C4;
            background: transparent;
            border: none;
        }
        #localStatus, #localInstallStatus {
            color: #DCE5F3;
            background: #1A2231;
            border: 1px solid #354057;
            border-radius: 9px;
            padding: 9px;
        }
        #capabilityBox {
            color: #EAF0F8;
            background: #1A2231;
            border: 1px solid #354057;
            border-radius: 10px;
            padding: 12px;
        }
        QScrollArea#settingsScroll { background: #121620; border: none; }
        QScrollBar:vertical { width: 8px; background: #121620; margin: 2px 0; }
        QScrollBar::handle:vertical { background: #46516A; border-radius: 4px; min-height: 30px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        self.setObjectName("SetupDialog")
        self._toggle_local_controls(self.local_enabled.isChecked())
        QTimer.singleShot(0, lambda: self._check_local_ai(show_message=False))

    @staticmethod
    def _eye_icon() -> QIcon:
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2.2 12s3.4-6 9.8-6 9.8 6 9.8 6-3.4 6-9.8 6-9.8-6-9.8-6Z"/><circle cx="12" cy="12" r="2.6"/></svg>'
        pixmap = QPixmap(); pixmap.loadFromData(QByteArray(svg), "SVG"); return QIcon(pixmap)

    @classmethod
    def _make_eye_button(cls, field: QLineEdit) -> QToolButton:
        button = QToolButton(); button.setObjectName("apiKeyEye"); button.setCheckable(True); button.setIcon(cls._eye_icon()); button.setToolTip("Show API key"); button.toggled.connect(lambda visible, target=field, eye=button: cls._toggle_key_visibility(target, eye, visible)); return button

    @staticmethod
    def _toggle_key_visibility(field: QLineEdit, button: QToolButton, visible: bool) -> None:
        field.setEchoMode(QLineEdit.Normal if visible else QLineEdit.Password); button.setToolTip("Hide API key" if visible else "Show API key")

    def _toggle_backup_visibility(self, visible: bool) -> None:
        self.backup_fields_container.setVisible(visible)
        self.show_backups.setText("Hide backup API keys" if visible else "Show backup API keys")
        scroll = self.findChild(QScrollArea, "settingsScroll")
        if scroll is not None:
            scroll.ensureWidgetVisible(self.backup_fields_container if visible else self.show_backups)
        QTimer.singleShot(0, lambda: self._keep_settings_geometry())

    def _keep_settings_geometry(self) -> None:
        size = self.size()
        self.resize(size)

    def _toggle_local_controls(self, enabled: bool) -> None:
        self.local_model.setEnabled(enabled); self.local_base_url.setEnabled(enabled); self.local_check.setEnabled(enabled); self.local_install.setEnabled(enabled)

    def _local_engine_from_form(self) -> LocalAIEngine:
        engine = LocalAIEngine(); engine.enabled = self.local_enabled.isChecked(); engine.base_url = self.local_base_url.text().strip().rstrip("/") or LocalAIEngine.DEFAULT_BASE_URL; engine.model = self.local_model.text().strip() or LocalAIEngine.DEFAULT_MODEL; return engine

    def _check_local_ai(self, show_message: bool = True) -> None:
        if not self.local_enabled.isChecked(): self.local_status.setText("Local AI status: disabled. Cloud AI will be used."); return
        try:
            status = self._local_engine_from_form().status()
            if status["available"]: self.local_status.setText(f"Local AI: ready\nModel: {status['model']}\nRuntime: Ollama-compatible endpoint detected.")
            elif status.get("ollama_installed"): self.local_status.setText(f"Local AI: Ollama detected, but the model/runtime is not ready.\n\n{status['reason']}")
            else: self.local_status.setText("Local AI: not available. Cloud AI will be used automatically.")
        except Exception as exc:
            self.local_status.setText(f"Local AI: unavailable — {exc}\nCloud AI will be used automatically.")
            if show_message: self._show_local_error("Local AI unavailable", str(exc))

    @staticmethod
    def _show_local_error(title: str, message: str) -> None:
        box = QMessageBox()
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(title)
        box.setText(message)
        box.setStandardButtons(QMessageBox.Ok)
        box.setStyleSheet("""
            QMessageBox { background: #121620; color: #F1F5F9; }
            QMessageBox QLabel { color: #EAF0F8; background: transparent; }
            QMessageBox QPushButton { color: #FFFFFF; background: #2A3346; border: 1px solid #53617A; border-radius: 7px; padding: 8px 18px; min-width: 70px; }
            QMessageBox QPushButton:hover { background: #3A4963; }
        """)
        box.exec()

    @staticmethod
    def _format_bytes(value: int) -> str:
        size = float(max(0, value))
        for unit in ("B", "MB", "GB"):
            if size < 1024 or unit == "GB":
                return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
            size /= 1024
        return f"{size:.1f} GB"

    def _install_local_model(self) -> None:
        engine = self._local_engine_from_form()
        if not engine.ollama_executable:
            self._show_local_error("Ollama required", "Ollama was not detected. Install Ollama, then use Install model again.")
            return
        if self._local_installer is not None and self._local_installer.isRunning():
            return
        model = engine.model
        self.local_install.setEnabled(False)
        self.local_check.setEnabled(False)
        self.local_progress.setVisible(True)
        self.local_progress.setRange(0, 100)
        self.local_progress.setValue(0)
        self.local_install_status.setText(f"Starting download of {model}…")
        self.local_status.setText(f"Local AI: downloading {model}. Keep this window open.")
        self._local_installer = _LocalInstaller(engine, model)
        self._local_installer.progress.connect(self._local_install_progress)
        self._local_installer.completed.connect(self._local_install_done)
        self._local_installer.failed.connect(self._local_install_failed)
        self._local_installer.finished.connect(self._local_installer.deleteLater)
        self._local_installer.start()

    def _local_install_progress(self, status: str, completed: int, total: int) -> None:
        status_lower = status.lower()
        if total > 0:
            percent = max(0, min(100, int((completed / total) * 100)))
            self.local_progress.setRange(0, 100)
            self.local_progress.setValue(percent)
            self.local_install_status.setText(f"{status} — {percent}% ({self._format_bytes(completed)} / {self._format_bytes(total)})")
        else:
            self.local_progress.setRange(0, 0)
            self.local_install_status.setText(status or "Working…")
        if "pull" in status_lower or "download" in status_lower or "writing" in status_lower or "verif" in status_lower:
            self.local_status.setText(f"Local AI: {status or 'working…'}")

    def _local_install_done(self, message: str) -> None:
        self.local_progress.setRange(0, 100)
        self.local_progress.setValue(100)
        self.local_install_status.setText("Download complete. Verifying local model…")
        self.local_status.setText(f"Local AI: {self.local_model.text().strip()} installed. Checking availability…")
        self._check_local_ai(show_message=False)
        self.local_install.setEnabled(self.local_enabled.isChecked())
        self.local_check.setEnabled(self.local_enabled.isChecked())
        self.local_progress.setVisible(False)
        self.local_install_status.setText("✓ Model installed and ready")
        box = QMessageBox()
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle("Local AI ready")
        box.setText(f"The local model is installed and ready.\n\n{message}")
        box.setStandardButtons(QMessageBox.Ok)
        box.setStyleSheet("""
            QMessageBox { background: #121620; color: #F1F5F9; }
            QMessageBox QLabel { color: #EAF0F8; background: transparent; }
            QMessageBox QPushButton { color: #FFFFFF; background: #2A3346; border: 1px solid #53617A; border-radius: 7px; padding: 8px 18px; min-width: 70px; }
            QMessageBox QPushButton:hover { background: #3A4963; }
        """)
        box.exec()

    def _local_install_failed(self, message: str) -> None:
        self.local_progress.setVisible(False)
        self.local_install_status.setText("Installation failed — see the error message.")
        self.local_status.setText("Local AI: installation failed. The existing local AI setup was not changed.")
        self.local_install.setEnabled(self.local_enabled.isChecked())
        self.local_check.setEnabled(self.local_enabled.isChecked())
        self._show_local_error("Ollama could not install the model", message)

    def _provider_for_form(self) -> AIProvider:
        provider = AIProvider(); provider.provider = self.provider.text().strip(); provider.api_key = self.api_key.text().strip(); provider.api_keys = [provider.api_key] if provider.api_key else []
        for field in self.backup_keys:
            key = field.text().strip()
            if key and key not in provider.api_keys: provider.api_keys.append(key)
        provider.base_url = self.base_url.text().strip(); provider.model = self.model.currentText().strip(); return provider

    def _refresh_models(self) -> None:
        if self._loader is not None and self._loader.isRunning(): return
        try:
            provider = self._provider_for_form()
            if not provider.configured and not provider.provider: QMessageBox.information(self, "Provider required", "Enter an API key or base URL first."); return
            self.model.setEnabled(False); self._loader = _ModelLoader(provider); self._loader.models_loaded.connect(self._models_loaded); self._loader.load_failed.connect(self._models_failed); self._loader.finished.connect(self._loader.deleteLater); self._loader.start()
        except Exception as exc: QMessageBox.warning(self, "Could not load models", str(exc))

    def _models_loaded(self, models: list) -> None:
        current = self.model.currentText().strip(); self.model.clear(); self.model.addItem("")
        for model in models: self.model.addItem(str(model))
        if current:
            index = self.model.findText(current); self.model.setCurrentIndex(index) if index >= 0 else self.model.setCurrentText(current)
        self.model.setEnabled(True)

    def _models_failed(self, message: str) -> None: self.model.setEnabled(True); QMessageBox.warning(self, "Could not load models", message)

    def _check_capabilities(self) -> None:
        try:
            provider = self._provider_for_form(); caps = provider.capabilities(provider.model or None); labels = caps.labels(); self.capability_box.setText("Capabilities\n" + ("\n".join("✓ " + label for label in labels) if labels else "No cloud capabilities detected.") + ("\n✗ Vision" if not caps.vision else ""))
        except Exception as exc: self.capability_box.setText(f"Capabilities\nCould not determine capabilities: {exc}")

    def _connect_google(self) -> None:
        config = read_config()
        if not config.get("GMAIL_CLIENT_ID", "").strip():
            wizard = GoogleSetupDialog(self)
            if wizard.exec() != QDialog.Accepted: return
        self.google_status.setText("Opening Google sign-in in your browser…"); self._google_login = _GoogleLogin(); self._google_login.connected.connect(self._google_connected); self._google_login.failed.connect(self._google_failed); self._google_login.finished.connect(self._google_login.deleteLater); self._google_login.start()

    def _google_connected(self, message: str) -> None: self.google_status.setText("✓ Google account connected")
    def _google_failed(self, message: str) -> None: self.google_status.setText("Sign-in needs attention — click Help for guidance"); QMessageBox.warning(self, "Google sign-in", message)
    def _open_help(self) -> None:
        try: HelpDialog(self).exec()
        except Exception as exc: QMessageBox.critical(self, "Help could not be opened", f"The help window could not be opened.\n\n{exc}")

    def _save(self) -> None:
        try:
            save_provider_name(self.provider.text()); save_api_key(self.api_key.text()); save_backup_api_keys([field.text() for field in self.backup_keys]); save_base_url(self.base_url.text()); save_model(self.model.currentText().strip()); save_local_ai(self.local_enabled.isChecked(), self.local_base_url.text().strip() or LocalAIEngine.DEFAULT_BASE_URL, self.local_model.text().strip() or LocalAIEngine.DEFAULT_MODEL); save_routing_mode(self.routing.currentText())
        except OSError as exc:
            QMessageBox.critical(self, "Could not save settings", str(exc)); return
        self.accept()
