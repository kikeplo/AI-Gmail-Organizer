"""Desktop overlay for AI Gmail Organizer."""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QTabWidget, QVBoxLayout, QWidget,
)

from app.agent.commands import CommandAgent
from app.memory.store import MemoryStore
from app.ui.dashboard import HistoryView, UsageView
from app.ui.setup_dialog import SetupDialog
from app.ui.worker import CommandWorker


class OverlayWindow(QMainWindow):
    """Unified desktop interface for assistant, history, and usage."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AI Gmail Organizer")
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(780, 540)
        self.resize(960, 680)
        self._drag_position = None
        self._agent = CommandAgent()
        self._memory = MemoryStore()
        self._pending_action = None
        self._thread: QThread | None = None
        self._worker: CommandWorker | None = None
        self._build_ui()
        self._add_message("assistant", "AI Gmail Organizer is ready. Ask me to organize Gmail, inspect the active window, or run a supported workflow.")

    def _build_ui(self) -> None:
        root = QWidget(); root.setObjectName("root"); self.setCentralWidget(root)
        layout = QVBoxLayout(root); layout.setContentsMargins(18, 18, 18, 18)
        panel = QFrame(); panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel); panel_layout.setContentsMargins(24, 20, 24, 20); panel_layout.setSpacing(14)
        header = QHBoxLayout(); title_block = QVBoxLayout(); title_block.setSpacing(2)
        title = QLabel("AI Gmail Organizer"); title.setObjectName("title")
        subtitle = QLabel("v1.0 • Gmail + Windows + local memory"); subtitle.setObjectName("subtitle")
        title_block.addWidget(title); title_block.addWidget(subtitle)
        self.status = QLabel("● Ready"); self.status.setObjectName("status")
        settings = QPushButton("Settings"); settings.setObjectName("settingsButton"); settings.clicked.connect(self._open_settings)
        minimize = QPushButton("—"); minimize.setObjectName("minimizeButton"); minimize.setFixedSize(38, 38); minimize.setToolTip("Minimize"); minimize.clicked.connect(self.showMinimized)
        close = QPushButton("×"); close.setObjectName("closeButton"); close.setFixedSize(38, 38); close.setToolTip("Close"); close.clicked.connect(self.close)
        header.addLayout(title_block); header.addStretch(); header.addWidget(self.status); header.addSpacing(8); header.addWidget(settings); header.addSpacing(4); header.addWidget(minimize); header.addSpacing(4); header.addWidget(close)
        panel_layout.addLayout(header)
        self.tabs = QTabWidget(); self.tabs.setObjectName("mainTabs")
        self.chat_page = self._build_chat_page(); self.history_view = HistoryView(self._memory); self.usage_view = UsageView(self._memory)
        self.tabs.addTab(self.chat_page, "Assistant"); self.tabs.addTab(self.history_view, "History"); self.tabs.addTab(self.usage_view, "Usage"); self.tabs.currentChanged.connect(self._refresh_dashboard)
        panel_layout.addWidget(self.tabs, 1); layout.addWidget(panel)
        self.setStyleSheet("""
            QWidget#root { background: transparent; }
            QFrame#panel { background: rgba(18,22,32,250); border: 1px solid rgba(255,255,255,30); border-radius: 24px; }
            QLabel#title { color: #F8FAFC; font-size: 22px; font-weight: 700; }
            QLabel#subtitle { color: #AEB7C7; font-size: 12px; }
            QLabel#status { color: #7FE08A; font-size: 12px; font-weight: 700; }
            QTabWidget#mainTabs::pane { border: none; }
            QTabBar::tab { color: #9FA9BA; background: transparent; border: none; border-radius: 9px; padding: 9px 16px; font-weight: 700; margin-right: 4px; }
            QTabBar::tab:hover { color: #FFFFFF; background: rgba(255,255,255,10); }
            QTabBar::tab:selected { color: #FFFFFF; background: rgba(79,108,247,48); }
            QPushButton#settingsButton { color: #E1E6EE; background: rgba(255,255,255,10); border: 1px solid rgba(255,255,255,24); border-radius: 11px; padding: 9px 12px; }
            QPushButton#settingsButton:hover { color: #FFFFFF; background: rgba(79,108,247,45); }
            QPushButton#minimizeButton, QPushButton#closeButton { color: #E1E6EE; background: rgba(255,255,255,10); border: none; border-radius: 11px; font-size: 21px; }
            QPushButton#minimizeButton:hover { background: rgba(255,255,255,28); color: #FFFFFF; }
            QPushButton#closeButton:hover { background: rgba(255,80,80,45); color: #FFFFFF; }
            QLabel#section { color: #E3E8F0; font-size: 12px; font-weight: 700; }
            QLabel#hint { color: #A6AFBE; font-size: 11px; padding: 2px 4px; }
            QScrollArea#messagesScroll { background: transparent; border: none; }
            QAbstractScrollArea::viewport { background: transparent; }
            QScrollBar:vertical { width: 7px; background: transparent; }
            QScrollBar::handle:vertical { background: rgba(255,255,255,55); border-radius: 3px; min-height: 24px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QPushButton#quickButton { color: #E1E6EE; background: rgba(255,255,255,10); border: 1px solid rgba(255,255,255,24); border-radius: 11px; padding: 9px 12px; }
            QPushButton#quickButton:hover { color: #FFFFFF; background: rgba(79,108,247,45); }
            QLabel#messageUser, QLabel#messageAssistant { color: #F1F5F9; font-size: 14px; padding: 13px 15px; border-radius: 15px; }
            QLabel#messageUser { background: rgba(65,86,170,225); border: 1px solid rgba(120,145,255,70); }
            QLabel#messageAssistant { background: rgba(38,45,60,235); border: 1px solid rgba(255,255,255,18); }
            QLineEdit { color: #F7F8FA; selection-color: #FFFFFF; selection-background-color: #4F6CF7; background: rgba(255,255,255,13); border: 1px solid rgba(255,255,255,28); border-radius: 13px; padding: 13px 14px; font-size: 14px; }
            QLineEdit::placeholder { color: #98A3B5; }
            QLineEdit:focus { border: 1px solid rgba(120,150,255,180); }
            QPushButton#sendButton { color: #FFFFFF; background: #4F6CF7; border: none; border-radius: 13px; padding: 11px 20px; font-weight: 700; }
            QPushButton#sendButton:hover { background: #607BFA; }
            QPushButton#sendButton:disabled { background: #30384E; color: #9AA4B4; }
        """)

    def _build_chat_page(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(12)
        section = QLabel("Quick actions"); section.setObjectName("section"); layout.addWidget(section)
        quick_row = QHBoxLayout()
        for label, command in (("Organize inbox", "Organize my inbox"), ("Unread", "Find my unread Gmail emails"), ("Active window", "What window is active?")):
            button = QPushButton(label); button.setObjectName("quickButton"); button.clicked.connect(lambda _checked=False, value=command: self._submit(value)); quick_row.addWidget(button)
        layout.addLayout(quick_row)
        self.messages = QVBoxLayout(); self.messages.setSpacing(10); self.messages.addStretch()
        host = QWidget(); host.setLayout(self.messages); self.scroll = QScrollArea(); self.scroll.setWidget(host); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.NoFrame); self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self.scroll.setObjectName("messagesScroll"); layout.addWidget(self.scroll, 1)
        self.hint = QLabel("Gmail changes require confirmation. Local memory stays on this machine."); self.hint.setObjectName("hint"); layout.addWidget(self.hint)
        input_row = QHBoxLayout(); self.command_input = QLineEdit(); self.command_input.setPlaceholderText("Ask for a Gmail, desktop, or memory workflow…"); self.command_input.setClearButtonEnabled(True)
        self.send_button = QPushButton("Send"); self.send_button.setObjectName("sendButton"); self.send_button.setMinimumWidth(94); self.send_button.clicked.connect(self._on_send); self.command_input.returnPressed.connect(self._on_send); input_row.addWidget(self.command_input); input_row.addWidget(self.send_button); layout.addLayout(input_row)
        return page

    def _refresh_dashboard(self, index: int) -> None:
        if index == 1: self.history_view.store = self._memory; self.history_view.refresh()
        elif index == 2: self.usage_view.store = self._memory; self.usage_view.refresh()

    def _add_message(self, role: str, text: str) -> None:
        label = QLabel(text); label.setObjectName("messageUser" if role == "user" else "messageAssistant"); label.setWordWrap(True); label.setTextInteractionFlags(Qt.TextSelectableByMouse); label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum); self.messages.insertWidget(self.messages.count() - 1, label); self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

    def _submit(self, command: str) -> None: self.tabs.setCurrentIndex(0); self.command_input.setText(command); self._on_send()

    def _on_send(self) -> None:
        command = self.command_input.text().strip()
        if not command or self._thread is not None: return
        self._add_message("user", command); self.command_input.clear(); self.send_button.setEnabled(False); self.send_button.setText("Working…"); self.status.setText("● Working"); self.hint.setText("Processing in the background — the window remains responsive.")
        self._thread = QThread(self); self._worker = CommandWorker(self._agent, command); self._worker.moveToThread(self._thread); self._thread.started.connect(self._worker.run); self._worker.finished.connect(self._on_worker_finished); self._worker.failed.connect(self._on_worker_failed); self._worker.finished.connect(self._thread.quit); self._worker.failed.connect(self._thread.quit); self._thread.finished.connect(self._cleanup_worker); self._thread.start()

    def _on_worker_finished(self, response) -> None:
        self._add_message("assistant", response.text); self._pending_action = response.pending_action
        if response.mode == "confirmation" and self._pending_action is not None:
            reply = QMessageBox.question(self, "Confirm Gmail action", response.text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No); follow_up = self._agent.confirm_action(self._pending_action, reply == QMessageBox.Yes); self._add_message("assistant", follow_up.text); self._pending_action = None
        self._set_ready_state()

    def _on_worker_failed(self, message: str) -> None: self._add_message("assistant", f"The command could not be completed.\n\n{message}"); self._set_ready_state()

    def _set_ready_state(self) -> None: self.send_button.setEnabled(True); self.send_button.setText("Send"); self.status.setText("● Ready"); self.hint.setText("Gmail changes require confirmation. Local memory stays on this machine.")

    def _cleanup_worker(self) -> None:
        if self._worker is not None: self._worker.deleteLater()
        if self._thread is not None: self._thread.deleteLater()
        self._worker = None; self._thread = None

    def _open_settings(self) -> None:
        dialog = SetupDialog(self)
        if dialog.exec() == QDialog.Accepted:
            from dotenv import load_dotenv
            from app.config.user_settings import ENV_FILE
            load_dotenv(ENV_FILE, override=True)
            self._agent = CommandAgent()
            self._add_message("assistant", "Settings updated. The new AI provider is active now — no restart required.")
        self.history_view.store = self._memory; self.usage_view.store = self._memory

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton: self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft(); event.accept()
        else: super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_position is not None and event.buttons() & Qt.LeftButton: self.move(event.globalPosition().toPoint() - self._drag_position); event.accept()
        else: super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None: self._drag_position = None; super().mouseReleaseEvent(event)
