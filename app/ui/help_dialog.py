"""User-friendly help and setup guidance."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.agent.commands import CommandAgent


class HelpDialog(QDialog):
    """Guided setup help with a safe embedded assistant."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Gmail Organizer — Help")
        self.setMinimumSize(760, 620)
        self._agent = CommandAgent()
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        title = QLabel("Help & setup")
        title.setObjectName("helpTitle")
        subtitle = QLabel("Everything you need to connect Gmail and configure your AI provider.")
        subtitle.setObjectName("helpSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        tabs = QTabWidget()
        guide = QTextBrowser()
        guide.setOpenExternalLinks(True)
        guide.setHtml(
            """
            <h2>Connect Gmail</h2>
            <p><b>1. Sign in with Google</b><br>Open Settings and choose <b>Sign in with Google</b>. A normal browser window will open.</p>
            <p><b>2. Choose your account</b><br>Sign in to the Google account you want the Organizer to manage.</p>
            <p><b>3. Allow access</b><br>Review the requested Gmail permissions and allow access.</p>
            <p><b>4. Return to the app</b><br>The app stores the authorization locally so you normally will not need to sign in again.</p>
            <h2>AI provider</h2>
            <p>Enter an API key and/or API base URL in Settings. Use <b>Refresh models</b> to see models supplied by the provider.</p>
            <p>The app supports common AI protocols including Gemini, Anthropic, Ollama and OpenAI-compatible services.</p>
            <h2>Stuck?</h2>
            <p>Open the <b>Ask the Assistant</b> tab and describe what you see. You can ask things like:</p>
            <ul><li>"I cannot connect Gmail."</li><li>"Google says my app needs verification."</li><li>"Which API base URL should I use?"</li><li>"Why can't I see any models?"</li></ul>
            """
        )
        tabs.addTab(guide, "Setup guide")
        tabs.addTab(self._build_assistant_tab(), "Ask the Assistant")
        root.addWidget(tabs, 1)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close)
        root.addLayout(row)

        self.setStyleSheet(
            """
            QDialog { background: #121620; color: #F8FAFC; }
            QLabel#helpTitle { color: #F8FAFC; font-size: 22px; font-weight: 800; }
            QLabel#helpSubtitle { color: #AEB7C7; font-size: 12px; }
            QTabWidget::pane { border: 1px solid #30394B; border-radius: 12px; }
            QTabBar::tab { color: #AEB7C7; background: transparent; border: none; padding: 10px 16px; }
            QTabBar::tab:selected { color: #FFFFFF; background: rgba(79,108,247,48); border-radius: 8px; }
            QTextBrowser#guide, QTextBrowser#helpChat { color: #F1F5F9; background: #171D2A; border: none; padding: 14px; }
            QTextBrowser#guide a { color: #8EA5FF; }
            QLineEdit { color: #F7F8FA; background: #202738; border: 1px solid #3A4356; border-radius: 10px; padding: 11px 12px; }
            QPushButton { color: #F7F8FA; background: #2A3346; border: 1px solid #46516A; border-radius: 9px; padding: 9px 14px; }
            QPushButton:hover { background: #35415B; }
            QPushButton#helpSend { background: #4F6CF7; border: none; font-weight: 700; }
            """
        )

    def _build_assistant_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        chat = QTextBrowser()
        chat.setObjectName("helpChat")
        chat.setOpenExternalLinks(True)
        chat.setHtml(
            "<p><b>Assistant</b></p><p>Tell me what you are stuck on. I can explain the setup step by step.</p>"
        )
        layout.addWidget(chat, 1)
        self._help_chat = chat

        row = QHBoxLayout()
        self._help_input = QLineEdit()
        self._help_input.setPlaceholderText("Ask how to connect Gmail, configure an API, or fix an error…")
        self._help_input.returnPressed.connect(self._ask_assistant)
        send = QPushButton("Ask")
        send.setObjectName("helpSend")
        send.clicked.connect(self._ask_assistant)
        row.addWidget(self._help_input, 1)
        row.addWidget(send)
        layout.addLayout(row)
        return page

    def _ask_assistant(self) -> None:
        question = self._help_input.text().strip()
        if not question:
            return
        self._help_input.clear()
        self._help_chat.append(f"<p><b>You</b><br>{self._escape(question)}</p>")
        try:
            response = self._agent.respond(question)
            text = self._escape(response.text).replace("\n", "<br>")
            self._help_chat.append(f"<p><b>Assistant</b><br>{text}</p>")
        except Exception as exc:
            self._help_chat.append(
                f"<p><b>Assistant</b><br>I could not answer that safely right now.<br>{self._escape(str(exc))}</p>"
            )
        scrollbar = self._help_chat.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @staticmethod
    def _escape(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
