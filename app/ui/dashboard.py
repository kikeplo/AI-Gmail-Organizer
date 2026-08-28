"""Visual dashboard views for local history and usage."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QProgressBar, QVBoxLayout, QWidget

from app.memory.store import MemoryStore


class StatCard(QFrame):
    def __init__(self, label: str, value: str, detail: str = "") -> None:
        super().__init__()
        self.setObjectName("statCard")
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
            entry = QListWidgetItem(label)
            self.list.addItem(entry)


class UsageView(QWidget):
    def __init__(self, store: MemoryStore) -> None:
        super().__init__()
        self.store = store
        self.layout = QVBoxLayout(self)
        self.setStyleSheet("""
            QLabel#usageTitle, QLabel#usageSubtitle, QLabel#usageSection,
            QLabel#usageModeName, QLabel#usageModeValue { color: #F8FAFC; }
            QLabel#usageTitle { font-size: 20px; font-weight: 700; }
            QLabel#usageSubtitle { color: #D6DCE7; font-size: 12px; }
            QLabel#usageSection { font-size: 12px; font-weight: 700; margin-top: 8px; }
            QLabel#usageModeName, QLabel#usageModeValue { font-size: 12px; }
            QProgressBar { background: rgba(255,255,255,18); border: none; border-radius: 5px; height: 10px; }
            QProgressBar::chunk { background: #6D86F7; border-radius: 5px; }
        """)
        self.refresh()

    def refresh(self) -> None:
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        total = self.store.count()
        counts = self.store.mode_counts()
        ai_count = sum(value for mode, value in counts.items() if mode != "classification" and "gmail" not in mode)
        gmail_count = sum(value for mode, value in counts.items() if "gmail" in mode or mode == "classification")

        title = QLabel("Usage")
        title.setObjectName("usageTitle")
        subtitle = QLabel("A quick look at how you use the assistant")
        subtitle.setObjectName("usageSubtitle")
        self.layout.addWidget(title)
        self.layout.addWidget(subtitle)

        cards = QHBoxLayout()
        cards.addWidget(StatCard("Interactions", str(total), "Saved locally on this device"))
        cards.addWidget(StatCard("AI responses", str(ai_count), "Requests routed through the configured AI provider"))
        cards.addWidget(StatCard("Gmail workflows", str(gmail_count), "Search, classification, and Gmail actions"))
        self.layout.addLayout(cards)

        section = QLabel("Activity by mode")
        section.setObjectName("usageSection")
        self.layout.addWidget(section)

        max_count = max(counts.values(), default=1)
        for mode, count in counts.items():
            row = QHBoxLayout()
            name = QLabel(mode.replace("_", " ").title())
            name.setObjectName("usageModeName")
            name.setMinimumWidth(130)
            bar = QProgressBar()
            bar.setRange(0, max_count)
            bar.setValue(count)
            bar.setTextVisible(False)
            value = QLabel(str(count))
            value.setObjectName("usageModeValue")
            value.setMinimumWidth(30)
            row.addWidget(name)
            row.addWidget(bar, 1)
            row.addWidget(value)
            self.layout.addLayout(row)

        self.layout.addStretch()
