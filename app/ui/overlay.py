"""Polished desktop overlay for AI Gmail Organizer."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from app.agent.commands import CommandAgent


class OverlayWindow(QMainWindow):
    """Unified command center for Gmail, Windows automation, and local memory."""

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
        self._pending_action = None
        self._build_ui()
        self._add_message("assistant", "AI Gmail Organizer is ready. Ask me to organize Gmail, inspect the active window, review history, or run a supported workflow.")

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(24, 20, 24, 20)
        panel_layout.setSpacing(14)

        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        title = QLabel("AI Gmail Organizer")
        title.setObjectName("title")
        subtitle = QLabel("v1.0 • Gmail + Windows + local memory")
        subtitle.setObjectName("subtitle")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)

        status = QLabel("● Ready")
        status.setObjectName("status")
        close_button = QPushButton("×")
        close_button.setObjectName("closeButton")
        close_button.setFixedSize(38, 38)
        close_button.clicked.connect(self.close)
        header.addLayout(title_block)
        header.addStretch()
        header.addWidget(status)
        header.addSpacing(8)
        header.addWidget(close_button)
        panel_layout.addLayout(header)

        section = QLabel("Quick actions")
        section.setObjectName("section")
        panel_layout.addWidget(section)

        quick_row = QHBoxLayout()
        for label, command in (
            ("Organize inbox", "Organize my inbox"),
            ("Unread", "Find my unread Gmail emails"),
            ("Active window", "What window is active?"),
            ("History", "Show my history"),
            ("Usage", "Show usage analytics"),
        ):
            button = QPushButton(label)
            button.setObjectName("quickButton")
            button.clicked.connect(lambda _checked=False, value=command: self._submit(value))
            quick_row.addWidget(button)
        panel_layout.addLayout(quick_row)

        self.messages = QVBoxLayout()
        self.messages.setSpacing(10)
        self.messages.addStretch()
        scroll_host = QWidget()
        scroll_host.setObjectName("scrollHost")
        scroll_host.setLayout(self.messages)

        scroll = QScrollArea()
        scroll.setWidget(scroll_host)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setObjectName("messagesScroll")
        panel_layout.addWidget(scroll, 1)

        hint = QLabel("Gmail changes require confirmation. Local memory stays on this machine.")
        hint.setObjectName("hint")
        panel_layout.addWidget(hint)

        input_row = QHBoxLayout()
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Ask for a Gmail, desktop, or memory workflow…")
        self.command_input.setClearButtonEnabled(True)
        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("sendButton")
        self.send_button.setMinimumWidth(94)
        self.send_button.clicked.connect(self._on_send)
        self.command_input.returnPressed.connect(self._on_send)
        input_row.addWidget(self.command_input)
        input_row.addWidget(self.send_button)
        panel_layout.addLayout(input_row)
        layout.addWidget(panel)

        self.setStyleSheet("""
            QWidget#root { background: transparent; }
            QFrame#panel { background: rgba(18,22,32,250); border: 1px solid rgba(255,255,255,30); border-radius: 24px; }
            QLabel#title { color: #F8FAFC; font-size: 22px; font-weight: 700; }
            QLabel#subtitle { color: #AEB7C7; font-size: 12px; }
            QLabel#status { color: #7FE08A; font-size: 12px; font-weight: 700; }
            QLabel#section { color: #E3E8F0; font-size: 12px; font-weight: 700; }
            QLabel#hint { color: #A6AFBE; font-size: 11px; padding: 2px 4px; }
            QScrollArea#messagesScroll { background: transparent; border: none; }
            QScrollArea#messagesScroll > QWidget > QWidget#scrollHost { background: transparent; }
            QAbstractScrollArea::viewport { background: transparent; }
            QScrollBar:vertical { width: 7px; background: transparent; }
            QScrollBar::handle:vertical { background: rgba(255,255,255,55); border-radius: 3px; min-height: 24px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QPushButton#quickButton { color: #E1E6EE; background: rgba(255,255,255,10); border: 1px solid rgba(255,255,255,24); border-radius: 11px; padding: 9px 12px; }
            QPushButton#quickButton:hover { color: #FFFFFF; background: rgba(79,108,247,45); border-color: rgba(120,150,255,90); }
            QLabel#messageUser, QLabel#messageAssistant { color: #F1F5F9; font-size: 14px; padding: 13px 15px; border-radius: 15px; }
            QLabel#messageUser { background: rgba(65,86,170,225); border: 1px solid rgba(120,145,255,70); }
            QLabel#messageAssistant { background: rgba(38,45,60,235); border: 1px solid rgba(255,255,255,18); }
            QLineEdit { color: #F7F8FA; selection-color: #FFFFFF; selection-background-color: #4F6CF7; background: rgba(255,255,255,13); border: 1px solid rgba(255,255,255,28); border-radius: 13px; padding: 13px 14px; font-size: 14px; }
            QLineEdit::placeholder { color: #98A3B5; }
            QLineEdit:focus { border: 1px solid rgba(120,150,255,180); background: rgba(255,255,255,16); }
            QPushButton#sendButton { color: #FFFFFF; background: #4F6CF7; border: none; border-radius: 13px; padding: 11px 20px; font-weight: 700; }
            QPushButton#sendButton:hover { background: #607BFA; }
            QPushButton#sendButton:disabled { background: #30384E; color: #9AA4B4; }
            QPushButton#closeButton { color: #E1E6EE; background: rgba(255,255,255,10); border: none; border-radius: 11px; font-size: 23px; }
            QPushButton#closeButton:hover { background: rgba(255,80,80,45); color: #FFFFFF; }
        """)

    def _add_message(self, role: str, text: str) -> None:
        label = QLabel(text)
        label.setObjectName("messageUser" if role == "user" else "messageAssistant")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.messages.insertWidget(self.messages.count() - 1, label)

    def _submit(self, command: str) -> None:
        self.command_input.setText(command)
        self._on_send()

    def _on_send(self) -> None:
        command = self.command_input.text().strip()
        if not command:
            return
        self._add_message("user", command)
        self.command_input.clear()
        self.send_button.setEnabled(False)
        self.send_button.setText("Working…")
        try:
            response = self._agent.respond(command)
            self._add_message("assistant", response.text)
            self._pending_action = response.pending_action
            if response.mode == "confirmation" and self._pending_action is not None:
                reply = QMessageBox.question(
                    self,
                    "Confirm Gmail action",
                    response.text,
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                follow_up = self._agent.confirm_action(self._pending_action, reply == QMessageBox.Yes)
                self._add_message("assistant", follow_up.text)
                self._pending_action = None
        finally:
            self.send_button.setEnabled(True)
            self.send_button.setText("Send")

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._drag_position is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self._drag_position = None
        super().mouseReleaseEvent(event)
