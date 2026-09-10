"""Desktop overlay for AI Gmail Organizer."""

from __future__ import annotations

import re

from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QTabWidget, QVBoxLayout, QWidget,
)

from app.agent.access import AccessManager
from app.agent.commands import CommandAgent
from app.memory.store import MemoryStore
from app.ui.dashboard import HistoryView, UsageView
from app.ui.desktop_access import DesktopAccessDialog
from app.ui.setup_dialog import SetupDialog
from app.ui.worker import CommandWorker
from app.version import APP_VERSION_TEXT


class OverlayWindow(QMainWindow):
    """Unified desktop interface for Gmail, Windows, AI, vision, and local memory."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"AI Gmail Organizer {APP_VERSION_TEXT}")
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(780, 540)
        self.resize(960, 680)
        self._drag_position = None
        self._agent = CommandAgent()
        self._memory = MemoryStore()
        self._pending_action = None
        self._thread = None
        self._worker = None
        self._settings_dialog = None
        self._build_ui()
        self._agent.windows.set_own_window(int(self.winId()))
        self._foreground_timer = QTimer(self)
        self._foreground_timer.setInterval(350)
        self._foreground_timer.timeout.connect(self._remember_external_window)
        self._foreground_timer.start()
        self._add_message("assistant", f"AI Gmail Organizer {APP_VERSION_TEXT} is ready. I can work with Gmail, Windows, visual desktop control, and local memory.")

    def _remember_external_window(self) -> None:
        try:
            self._agent.windows.tools.update_last_external_window()
        except Exception:
            pass

    def _build_ui(self) -> None:
        root = QWidget(); root.setObjectName("root"); self.setCentralWidget(root)
        layout = QVBoxLayout(root); layout.setContentsMargins(18, 18, 18, 18)
        panel = QFrame(); panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel); panel_layout.setContentsMargins(24, 20, 24, 20); panel_layout.setSpacing(14)
        header = QHBoxLayout(); title_block = QVBoxLayout(); title_block.setSpacing(2)
        title = QLabel("AI Gmail Organizer"); title.setObjectName("title")
        subtitle = QLabel(f"{APP_VERSION_TEXT} • Gmail + Windows + local AI context + vision"); subtitle.setObjectName("subtitle")
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
        self.setStyleSheet(self._style())

    @staticmethod
    def _style() -> str:
        return """
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
            QPushButton#quickButton, QPushButton#pauseButton, QPushButton#stopButton { color: #E1E6EE; background: rgba(255,255,255,10); border: 1px solid rgba(255,255,255,24); border-radius: 11px; padding: 9px 12px; }
            QPushButton#quickButton:hover, QPushButton#pauseButton:hover { color: #FFFFFF; background: rgba(79,108,247,45); }
            QPushButton#stopButton:hover { color: #FFFFFF; background: rgba(210,70,70,70); }
            QPushButton#pauseButton:disabled, QPushButton#stopButton:disabled { color: #667085; background: rgba(255,255,255,6); }
            QLabel#messageUser, QLabel#messageAssistant { color: #F1F5F9; font-size: 14px; padding: 13px 15px; border-radius: 15px; }
            QLabel#messageUser { background: rgba(65,86,170,225); border: 1px solid rgba(120,145,255,70); }
            QLabel#messageAssistant { background: rgba(38,45,60,235); border: 1px solid rgba(255,255,255,18); }
            QLineEdit { color: #F7F8FA; selection-color: #FFFFFF; selection-background-color: #4F6CF7; background: rgba(255,255,255,13); border: 1px solid rgba(255,255,255,28); border-radius: 13px; padding: 13px 14px; font-size: 14px; }
            QLineEdit::placeholder { color: #98A3B5; }
            QLineEdit:focus { border: 1px solid rgba(120,150,255,180); }
            QPushButton#sendButton { color: #FFFFFF; background: #4F6CF7; border: none; border-radius: 13px; padding: 11px 20px; font-weight: 700; }
            QPushButton#sendButton:hover { background: #607BFA; }
            QPushButton#sendButton:disabled { background: #30384E; color: #9AA4B4; }
        """

    def _build_chat_page(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(12)
        section = QLabel("Quick actions"); section.setObjectName("section"); layout.addWidget(section)
        quick_row = QHBoxLayout()
        for label, command in (("Organize inbox", "Organize my inbox"), ("Unread", "Find my unread Gmail emails"), ("Active window", "What window is active?")):
            button = QPushButton(label); button.setObjectName("quickButton"); button.clicked.connect(lambda _checked=False, value=command: self._submit(value)); quick_row.addWidget(button)
        layout.addLayout(quick_row)
        self.messages = QVBoxLayout(); self.messages.setSpacing(10); self.messages.addStretch()
        host = QWidget(); host.setLayout(self.messages); self.scroll = QScrollArea(); self.scroll.setWidget(host); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.NoFrame); self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self.scroll.setObjectName("messagesScroll"); layout.addWidget(self.scroll, 1)
        self.hint = QLabel("Gmail changes require confirmation. Desktop actions are performed on your local Windows session. Local memories stay on this device."); self.hint.setObjectName("hint"); layout.addWidget(self.hint)
        control_row = QHBoxLayout(); self.pause_button = QPushButton("⏸ Pause"); self.pause_button.setObjectName("pauseButton"); self.pause_button.setEnabled(False); self.pause_button.clicked.connect(self._toggle_pause); self.stop_button = QPushButton("⛔ Stop"); self.stop_button.setObjectName("stopButton"); self.stop_button.setEnabled(False); self.stop_button.clicked.connect(self._stop_task); control_row.addWidget(self.pause_button); control_row.addWidget(self.stop_button); control_row.addStretch(); layout.addLayout(control_row)
        input_row = QHBoxLayout(); self.command_input = QLineEdit(); self.command_input.setPlaceholderText("Ask me to work with Gmail, Windows, your screen, or your memories…"); self.command_input.setClearButtonEnabled(True); self.send_button = QPushButton("Send"); self.send_button.setObjectName("sendButton"); self.send_button.setMinimumWidth(94); self.send_button.clicked.connect(self._on_send); self.command_input.returnPressed.connect(self._on_send); input_row.addWidget(self.command_input); input_row.addWidget(self.send_button); layout.addLayout(input_row)
        return page

    @staticmethod
    def _clean_ai_text(text: str) -> str:
        text=text.replace("\r\n","\n").replace("\r","\n"); text=re.sub(r"^\s*([-*_])(?:\s*\1){2,}\s*$","",text,flags=re.MULTILINE); text=re.sub(r"^\s*#{1,6}\s*","",text,flags=re.MULTILINE); text=re.sub(r"^\s*[-*+]\s+","• ",text,flags=re.MULTILINE); text=text.replace("**","").replace("__",""); text=re.sub(r"(?<!\w)\*([^\n*]+)\*(?!\w)",r"\1",text); text=re.sub(r"(?<!\w)_([^\n_]+)_(?!\w)",r"\1",text); text=text.replace("```","").replace("`",""); text=re.sub(r"\n{3,}","\n\n",text); return text.strip()
    def _refresh_dashboard(self,index:int)->None:
        if index==1: self.history_view.store=self._memory; self.history_view.refresh()
        elif index==2: self.usage_view.store=self._memory; self.usage_view.refresh()
    def _add_message(self,role:str,text:str)->None:
        label=QLabel(self._clean_ai_text(text) if role=="assistant" else text); label.setObjectName("messageUser" if role=="user" else "messageAssistant"); label.setWordWrap(True); label.setTextInteractionFlags(Qt.TextSelectableByMouse); label.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Minimum); self.messages.insertWidget(self.messages.count()-1,label); self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())
    def _submit(self,command:str)->None: self.tabs.setCurrentIndex(0); self.command_input.setText(command); self._on_send()
    def _needs_visual_access(self,command:str)->bool:
        lowered=command.casefold(); return self._agent._looks_like_gmail_ui_task(lowered) or self._agent._looks_like_visual_task(lowered)
    def _request_visual_access(self)->bool:
        access=AccessManager()
        if access.is_allowed("screen") and access.is_allowed("input"): return True
        dialog=DesktopAccessDialog(access,parent=self); dialog.setWindowModality(Qt.ApplicationModal); dialog.setModal(True); dialog.raise_(); dialog.activateWindow()
        if dialog.exec()==QDialog.Accepted and access.is_allowed("screen") and access.is_allowed("input"): self._add_message("assistant","Screen and mouse/keyboard access enabled. Starting the visual task…"); return True
        self._add_message("assistant","Visual task cancelled because screen and mouse/keyboard access was not enabled."); return False
    def _on_send(self)->None:
        command=self.command_input.text().strip()
        if not command or self._thread is not None: return
        if self._needs_visual_access(command) and not self._request_visual_access(): return
        self._add_message("user",command); self.command_input.clear(); self.send_button.setEnabled(False); self.send_button.setText("Working…"); self.status.setText("● Working"); self.hint.setText("Working in the background. You can pause or stop a visual task at any time."); self.pause_button.setEnabled(True); self.stop_button.setEnabled(True)
        self._thread=QThread(self); self._worker=CommandWorker(self._agent,command); self._worker.moveToThread(self._thread); self._thread.started.connect(self._worker.run); self._worker.status.connect(self._on_worker_status); self._worker.finished.connect(self._on_worker_finished); self._worker.failed.connect(self._on_worker_failed); self._worker.finished.connect(self._thread.quit); self._worker.failed.connect(self._thread.quit); self._thread.finished.connect(self._cleanup_worker); self._thread.start()
    def _on_worker_status(self,message:str)->None: self.status.setText("● "+message); self.hint.setText(message)
    def _toggle_pause(self)->None:
        if self._thread is None: return
        if self._agent.vision.pause_requested: self._agent.resume_task(); self.pause_button.setText("⏸ Pause"); self.status.setText("● Working"); self.hint.setText("Task resumed.")
        else: self._agent.pause_task(); self.pause_button.setText("▶ Resume"); self.status.setText("● Paused"); self.hint.setText("Task paused. Resume when you are ready.")
    def _stop_task(self)->None:
        if self._thread is None: return
        self._agent.stop_task(); self.stop_button.setEnabled(False); self.pause_button.setEnabled(False); self.status.setText("● Stopping…"); self.hint.setText("Stopping the current task…")
    def _on_worker_finished(self,response)->None:
        self._add_message("assistant",response.text); self._pending_action=response.pending_action
        if response.mode=="confirmation" and self._pending_action is not None:
            reply=QMessageBox.question(self,"Confirm action",response.text,QMessageBox.Yes|QMessageBox.No,QMessageBox.No); follow_up=self._agent.confirm_action(self._pending_action,reply==QMessageBox.Yes); self._add_message("assistant",follow_up.text); self._pending_action=None
        self._set_ready_state()
    def _on_worker_failed(self,message:str)->None: self._add_message("assistant",f"The command could not be completed.\n\n{message}"); self._set_ready_state()
    def _set_ready_state(self)->None: self.send_button.setEnabled(True); self.send_button.setText("Send"); self.status.setText("● Ready"); self.hint.setText("Gmail changes require confirmation. Desktop actions are performed on your local Windows session. Local memories stay on this device."); self.pause_button.setEnabled(False); self.stop_button.setEnabled(False); self.pause_button.setText("⏸ Pause")
    def _cleanup_worker(self)->None:
        if self._worker is not None: self._worker.deleteLater()
        if self._thread is not None: self._thread.deleteLater()
        self._worker=None; self._thread=None

    def _open_settings(self) -> None:
        if self._settings_dialog is not None:
            try:
                self._settings_dialog.raise_(); self._settings_dialog.activateWindow(); return
            except RuntimeError: self._settings_dialog=None
        try:
            dialog=SetupDialog(self)
            self._settings_dialog=dialog
            screen=self.screen()
            if screen is not None:
                available=screen.availableGeometry(); width=min(820,max(620,available.width()-80)); height=min(760,max(480,available.height()-80)); dialog.resize(width,height); frame=dialog.frameGeometry(); frame.moveCenter(available.center()); dialog.move(frame.topLeft())
            dialog.setWindowModality(Qt.ApplicationModal); dialog.raise_(); dialog.activateWindow()
            result=dialog.exec()
            if result==QDialog.Accepted:
                from dotenv import load_dotenv
                from app.config.user_settings import ENV_FILE
                load_dotenv(ENV_FILE,override=True); self._agent=CommandAgent(); self._agent.windows.set_own_window(int(self.winId())); self._add_message("assistant","Settings updated. The new AI provider and local AI configuration are active now — no restart required.")
        except Exception as exc:
            QMessageBox.critical(self,"Settings could not be opened",f"The Settings window could not be opened.\n\n{exc}")
        finally: self._settings_dialog=None
        self.history_view.store=self._memory; self.usage_view.store=self._memory

    def mousePressEvent(self,event)->None:
        if event.button()==Qt.LeftButton: self._drag_position=event.globalPosition().toPoint()-self.frameGeometry().topLeft(); event.accept()
        else: super().mousePressEvent(event)
    def mouseMoveEvent(self,event)->None:
        if self._drag_position is not None and event.buttons() & Qt.LeftButton: self.move(event.globalPosition().toPoint()-self._drag_position); event.accept()
        else: super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event)->None: self._drag_position=None; super().mouseReleaseEvent(event)
