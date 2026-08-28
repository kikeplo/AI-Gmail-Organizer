"""Desktop overlay UI for v0.1."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class OverlayWindow(QMainWindow):
    """Borderless, always-on-top starter window for the desktop assistant."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AI Gmail Organizer")
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(760, 500)
        self.resize(860, 560)

        self._drag_position = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(22, 20, 22, 20)
        panel_layout.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("AI Gmail Organizer")
        title.setObjectName("title")
        subtitle = QLabel("v0.1 • desktop overlay")
        subtitle.setObjectName("subtitle")

        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        title_block.addWidget(title)
        title_block.addWidget(subtitle)

        close_button = QPushButton("×")
        close_button.setObjectName("closeButton")
        close_button.setFixedSize(36, 36)
        close_button.clicked.connect(self.close)

        header.addLayout(title_block)
        header.addStretch()
        header.addWidget(close_button)

        panel_layout.addLayout(header)

        welcome = QLabel(
            "Your AI Gmail workspace starts here.\n\n"
            "Next milestones: connect Gmail, add an AI agent, and let it organize your inbox."
        )
        welcome.setObjectName("welcome")
        welcome.setWordWrap(True)
        welcome.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        panel_layout.addWidget(welcome)

        input_row = QHBoxLayout()
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText(
            "Try: Show me what this assistant will eventually do..."
        )
        self.command_input.setClearButtonEnabled(True)

        send_button = QPushButton("Send")
        send_button.setObjectName("sendButton")
        send_button.setMinimumWidth(90)
        send_button.clicked.connect(self._on_send)
        self.command_input.returnPressed.connect(self._on_send)

        input_row.addWidget(self.command_input)
        input_row.addWidget(send_button)
        panel_layout.addLayout(input_row)

        layout.addWidget(panel)

        self.setStyleSheet(
            """
            QWidget#root { background: transparent; }
            QFrame#panel {
                background: rgba(20, 24, 34, 245);
                border: 1px solid rgba(255, 255, 255, 28);
                border-radius: 22px;
            }
            QLabel#title { color: #F7F8FA; font-size: 21px; font-weight: 700; }
            QLabel#subtitle { color: #9DA5B4; font-size: 12px; }
            QLabel#welcome {
                color: #C8CED8; font-size: 15px; padding: 18px;
                background: rgba(255, 255, 255, 10);
                border: 1px solid rgba(255, 255, 255, 16);
                border-radius: 14px;
            }
            QLineEdit {
                color: #F7F8FA; background: rgba(255, 255, 255, 12);
                border: 1px solid rgba(255, 255, 255, 22);
                border-radius: 12px; padding: 12px 14px; font-size: 14px;
            }
            QLineEdit:focus { border: 1px solid rgba(120, 150, 255, 150); }
            QPushButton#sendButton {
                color: #FFFFFF; background: #4F6CF7; border: none;
                border-radius: 12px; padding: 10px 18px; font-weight: 700;
            }
            QPushButton#sendButton:hover { background: #607BFA; }
            QPushButton#closeButton {
                color: #D7DCE5; background: rgba(255, 255, 255, 10);
                border: none; border-radius: 10px; font-size: 22px;
            }
            QPushButton#closeButton:hover { background: rgba(255, 80, 80, 40); }
            """
        )

    def _on_send(self) -> None:
        command = self.command_input.text().strip()
        if not command:
            return
        self.command_input.clear()

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
