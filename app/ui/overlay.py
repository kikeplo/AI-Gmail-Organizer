"""Interactive desktop overlay for v0.3."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from app.agent.commands import CommandAgent


class OverlayWindow(QMainWindow):
    """Borderless, always-on-top AI command surface."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AI Gmail Organizer")
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(760, 500)
        self.resize(860, 600)
        self._drag_position = None
        self._agent = CommandAgent()
        self._build_ui()
        self._add_message("assistant", "Hi! I’m your AI Gmail Organizer. Try 'Find my unread Gmail emails' to connect and search your inbox.")

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
        panel_layout.setContentsMargins(22, 18, 22, 18)
        panel_layout.setSpacing(12)

        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        title = QLabel("AI Gmail Organizer")
        title.setObjectName("title")
        subtitle = QLabel("v0.3 • Gmail connection")
        subtitle.setObjectName("subtitle")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        status = QLabel("● Ready")
        status.setObjectName("status")
        close_button = QPushButton("×")
        close_button.setObjectName("closeButton")
        close_button.setFixedSize(36, 36)
        close_button.clicked.connect(self.close)
        header.addLayout(title_block)
        header.addStretch()
        header.addWidget(status)
        header.addSpacing(8)
        header.addWidget(close_button)
        panel_layout.addLayout(header)

        self.messages = QVBoxLayout()
        self.messages.setSpacing(10)
        self.messages.addStretch()
        scroll_host = QWidget()
        scroll_host.setLayout(self.messages)
        scroll = QScrollArea()
        scroll.setWidget(scroll_host)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setObjectName("messagesScroll")
        panel_layout.addWidget(scroll, 1)

        hint = QLabel("Ask to search Gmail. The first Gmail command opens Google's secure OAuth sign-in.")
        hint.setObjectName("hint")
        panel_layout.addWidget(hint)
        input_row = QHBoxLayout()
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("e.g. Find unread emails from recruiters")
        self.command_input.setClearButtonEnabled(True)
        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("sendButton")
        self.send_button.setMinimumWidth(90)
        self.send_button.clicked.connect(self._on_send)
        self.command_input.returnPressed.connect(self._on_send)
        input_row.addWidget(self.command_input)
        input_row.addWidget(self.send_button)
        panel_layout.addLayout(input_row)
        layout.addWidget(panel)

        self.setStyleSheet("""
            QWidget#root { background: transparent; }
            QFrame#panel { background: rgba(20, 24, 34, 248); border: 1px solid rgba(255,255,255,28); border-radius: 22px; }
            QLabel#title { color: #F7F8FA; font-size: 21px; font-weight: 700; }
            QLabel#subtitle { color: #9DA5B4; font-size: 12px; }
            QLabel#status { color: #81D88A; font-size: 12px; font-weight: 600; }
            QLabel#hint { color: #747E90; font-size: 11px; padding: 2px 4px; }
            QScrollArea#messagesScroll { background: transparent; }
            QScrollBar:vertical { width: 7px; background: transparent; }
            QScrollBar::handle:vertical { background: rgba(255,255,255,35); border-radius: 3px; }
            QLabel#messageUser, QLabel#messageAssistant { color: #E7EBF2; font-size: 14px; padding: 12px 14px; border-radius: 14px; }
            QLabel#messageUser { background: rgba(79,108,247,55); }
            QLabel#messageAssistant { background: rgba(255,255,255,10); }
            QLineEdit { color: #F7F8FA; background: rgba(255,255,255,12); border: 1px solid rgba(255,255,255,22); border-radius: 12px; padding: 12px 14px; font-size: 14px; }
            QLineEdit:focus { border: 1px solid rgba(120,150,255,150); }
            QPushButton#sendButton { color: #FFFFFF; background: #4F6CF7; border: none; border-radius: 12px; padding: 10px 18px; font-weight: 700; }
            QPushButton#sendButton:hover { background: #607BFA; }
            QPushButton#sendButton:disabled { background: #30384E; }
            QPushButton#closeButton { color: #D7DCE5; background: rgba(255,255,255,10); border: none; border-radius: 10px; font-size: 22px; }
            QPushButton#closeButton:hover { background: rgba(255,80,80,40); }
        """)

    def _add_message(self, role: str, text: str) -> None:
        label = QLabel(text)
        label.setObjectName("messageUser" if role == "user" else "messageAssistant")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.messages.insertWidget(self.messages.count() - 1, label)

    def _on_send(self) -> None:
        command = self.command_input.text().strip()
        if not command:
            return
        self._add_message("user", command)
        self.command_input.clear()
        self.send_button.setEnabled(False)
        self.send_button.setText("...")
        response = self._agent.respond(command)
        self._add_message("assistant", response.text)
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
