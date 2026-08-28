"""Visual dashboard views for local history and usage."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QProgressBar, QVBoxLayout, QWidget

from app.memory.store import MemoryStore


class StatCard(QFrame):
    def __init__(self, label: str, value: str, detail: str = "") -> None:
        super().__init__()
        self.setObjectName("statCard")
        self.setStyleSheet("""
            QFrame#statCard { background: #1D2535; border: 1px solid #354057; border-radius: 14px; }
            QLabel#cardEyebrow, QLabel#cardValue, QLabel#cardDetail { color: #F8FAFC; }
            QLabel#cardEyebrow { color: #CBD5E1; font-size: 10px; font-weight: 700; }
            QLabel#cardValue { font-size: 26px; font-weight: 800; }
            QLabel#cardDetail { color: #CBD5E1; font-size: 11px; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        eyebrow = QLabel(label.upper())
        eyebrow.setObjectName("cardEyebrow")
        number = QLabel(value)
        number.setObjectName("cardValue")
        detail_label = QLabel(detail)
        detail_label.setObjectName("cardDetail")
        detail_label.setWordWrap(True)
        layout.addWidget(eyebrow)
        layout.addWidget(number)
        layout.addWidget(detail_label)


class HistoryView(QWidget):
    def __init__(self, store: MemoryStore) -> None:
        super().__init__()
        self.store = store
        layout = QVBoxLayout(self)
        title = QLabel("History")
        title.setObjectName("viewTitle")
        subtitle = QLabel("Your recent local assistant activity")
        subtitle.setObjectName("viewSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        self.list = QListWidget()
        self.list.setObjectName("historyList")
        layout.addWidget(self.list, 1)
        self.refresh()

    def refresh(self) -> None:
        self.list.clear()
        items = self.store.recent(30)
        if not items:
            empty = QListWidgetItem("No activity yet. Start with a command from the assistant.")
            empty.setTextAlignment(Qt.AlignCenter)
            self.list.addItem(empty)
            return
        for item in items:
            preview = item.response.splitlines()[0] if item.response else "No response"
            label = f"{item.command or '(empty command)'}\n{preview}\n{item.created_at.replace('T', ' ').split('+')[0]}"
            self.list.addItem(QListWidgetItem(label))


class UsageView(QWidget):
    def __init__(self, store: MemoryStore) -> None:
        super().__init__()
        self.store = store
        self.layout = QVBoxLayout(self)
        self.setStyleSheet("""
            QWidget { color: #F8FAFC; }
            QLabel#usageTitle, QLabel#usageSubtitle, QLabel#usageSection,
            QLabel#usageModeName, QLabel#usageModeValue { color: #F8FAFC; }
            QLabel#usageTitle { font-size: 20px; font-weight: 700; }
            QLabel#usageSubtitle { color: #D6DCE7; font-size: 12px; }
            QLabel#usageSection { font-size: 13px; font-weight: 700; margin-top: 10px; }
            QLabel#usageModeName { font-size: 12px; font-weight: 700; }
            QLabel#usageModeValue { color: #CBD5E1; font-size: 12px; font-weight: 700; }
            QFrame#modeRow { background: #1A2231; border: 1px solid #303A4E; border-radius: 10px; }
            QProgressBar { background: #30394B; border: none; border-radius: 4px; height: 8px; }
            QProgressBar::chunk { background: #6D86F7; border-radius: 4px; }
        """)
        self.refresh()

    @staticmethod
    def _mode_label(mode: str) -> str:
        mapping = {
            "gmail": "Gmail",
            "gmail_action": "Gmail action completed",
            "gmail_error": "Gmail errors",
            "gmail_setup": "Gmail setup",
            "gmail_search": "Gmail search",
            "classification": "Inbox organization",
            "analytics": "Analytics",
            "memory": "Memory",
            "demo": "Demo",
            "error": "Errors",
            "quota_error": "AI quota errors",
        }
        return mapping.get(mode, mode.replace("_", " ").title())

    def refresh(self) -> None:
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        total = self.store.count()
        counts = self.store.mode_counts()
        ai_count = sum(value for mode, value in counts.items() if mode.startswith("ai:") or mode in {"error", "quota_error"})
        # A Gmail workflow is counted only after a confirmed action has
        # actually been executed successfully. Searches, classifications,
        # setup attempts, confirmations, and errors do not increment it.
        gmail_count = counts.get("gmail_action", 0)

        title = QLabel("Usage")
        title.setObjectName("usageTitle")
        subtitle = QLabel("A quick look at how you use the assistant")
        subtitle.setObjectName("usageSubtitle")
        self.layout.addWidget(title)
        self.layout.addWidget(subtitle)

        cards = QHBoxLayout()
        cards.addWidget(StatCard("Interactions", str(total), "Saved locally on this device"))
        cards.addWidget(StatCard("AI responses", str(ai_count), "Requests routed through your configured provider"))
        cards.addWidget(StatCard("Gmail actions", str(gmail_count), "Successfully completed Gmail changes"))
        self.layout.addLayout(cards)

        section = QLabel("Activity by mode")
        section.setObjectName("usageSection")
        self.layout.addWidget(section)

        if not counts:
            empty = QLabel("No activity recorded yet.")
            empty.setStyleSheet("color: #AAB4C4; padding: 14px 2px;")
            self.layout.addWidget(empty)
        else:
            max_count = max(counts.values())
            for mode, count in counts.items():
                row_frame = QFrame()
                row_frame.setObjectName("modeRow")
                row = QHBoxLayout(row_frame)
                row.setContentsMargins(12, 9, 12, 9)
                name = QLabel(self._mode_label(mode))
                name.setObjectName("usageModeName")
                name.setMinimumWidth(145)
                bar = QProgressBar()
                bar.setRange(0, max_count)
                bar.setValue(count)
                bar.setTextVisible(False)
                value = QLabel(str(count))
                value.setObjectName("usageModeValue")
                value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                value.setMinimumWidth(32)
                row.addWidget(name)
                row.addWidget(bar, 1)
                row.addWidget(value)
                self.layout.addWidget(row_frame)

        self.layout.addStretch()
