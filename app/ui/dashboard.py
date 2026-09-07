"""Polished, readable dashboard views for local history and usage."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.memory.store import MemoryStore


class StatCard(QFrame):
    """Readable usage card with explicit high-contrast text and flexible sizing."""

    def __init__(self, label: str, value: str, detail: str = "") -> None:
        super().__init__()
        self.setObjectName("statCard")
        self.setMinimumHeight(124)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(
            """
            QFrame#statCard {
                background: #1D2535;
                border: 1px solid #354057;
                border-radius: 14px;
            }
            QLabel#cardEyebrow { color: #BFC9DA; font-size: 10px; font-weight: 800; }
            QLabel#cardValue { color: #FFFFFF; font-size: 25px; font-weight: 800; }
            QLabel#cardDetail { color: #D6DCE7; font-size: 11px; }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(4)
        eyebrow = QLabel(label.upper()); eyebrow.setObjectName("cardEyebrow")
        value_label = QLabel(value); value_label.setObjectName("cardValue")
        value_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        detail_label = QLabel(detail or "No data yet"); detail_label.setObjectName("cardDetail")
        detail_label.setWordWrap(True); detail_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout.addWidget(eyebrow); layout.addWidget(value_label); layout.addWidget(detail_label)


class HistoryView(QWidget):
    def __init__(self, store: MemoryStore) -> None:
        super().__init__()
        self.store = store
        self.setObjectName("historyView")
        self.setStyleSheet(
            """
            QWidget#historyView { background: #121620; }
            QLabel#historyTitle { color: #FFFFFF; font-size: 21px; font-weight: 800; }
            QLabel#historySubtitle { color: #B9C3D3; font-size: 12px; }
            QListWidget#historyList {
                background: #121620;
                border: none;
                color: #F8FAFC;
                outline: none;
                padding: 2px 0;
            }
            QListWidget#historyList::item {
                color: #F8FAFC;
                background: #1A2231;
                border: 1px solid #303A4E;
                border-radius: 10px;
                padding: 11px 13px;
                margin: 4px 1px;
            }
            QListWidget#historyList::item:selected {
                color: #FFFFFF;
                background: #263552;
            }
            QListWidget#historyList::item:hover {
                color: #FFFFFF;
                background: #202B3E;
            }
            QScrollBar:vertical { width: 8px; background: #121620; }
            QScrollBar::handle:vertical { background: #59657D; border-radius: 4px; min-height: 28px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        title = QLabel("History"); title.setObjectName("historyTitle")
        subtitle = QLabel("Your recent local assistant activity"); subtitle.setObjectName("historySubtitle")
        layout.addWidget(title); layout.addWidget(subtitle)
        self.list = QListWidget(); self.list.setObjectName("historyList")
        self.list.setWordWrap(True); self.list.setTextElideMode(Qt.ElideNone)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self.list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        palette = self.list.palette()
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.HighlightedText, Qt.white)
        palette.setColor(QPalette.Base, Qt.transparent)
        palette.setColor(QPalette.AlternateBase, Qt.transparent)
        self.list.setPalette(palette)
        layout.addWidget(self.list, 1)
        self.refresh()

    def refresh(self) -> None:
        self.list.clear()
        items = self.store.recent(100)
        if not items:
            empty = QListWidgetItem("No activity yet. Start with a command from the Assistant tab.")
            empty.setTextAlignment(Qt.AlignCenter); self.list.addItem(empty); return
        for item in items:
            preview = item.response.splitlines()[0] if item.response else "No response"
            timestamp = item.created_at.replace("T", " ").split("+")[0]
            self.list.addItem(QListWidgetItem(f"{item.command or '(empty command)'}\n{preview}\n{timestamp}"))


class UsageView(QWidget):
    def __init__(self, store: MemoryStore) -> None:
        super().__init__()
        self.setObjectName("usageView")
        self.setStyleSheet("QWidget#usageView { background: #121620; }")
        self.store = store
        self.outer_layout = QVBoxLayout(self); self.outer_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setStyleSheet("""
            QScrollArea { background: #121620; border: none; }
            QScrollArea > QWidget > QWidget { background: #121620; }
            QScrollBar:vertical { width: 8px; background: #121620; }
            QScrollBar::handle:vertical { background: #59657D; border-radius: 4px; min-height: 28px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        self.outer_layout.addWidget(self.scroll); self.refresh()

    @staticmethod
    def _mode_label(mode: str) -> str:
        mapping = {"gmail":"Gmail","gmail_action":"Gmail actions","gmail_error":"Gmail errors","gmail_setup":"Gmail setup","gmail_search":"Gmail search","classification":"Inbox organization","analytics":"Analytics","memory":"Memory","demo":"Demo","error":"Errors","quota_error":"AI quota errors"}
        return mapping.get(mode, mode.replace("_", " ").title())

    def refresh(self) -> None:
        content = QWidget(); content.setObjectName("usageContent")
        content.setStyleSheet("QWidget#usageContent { background: #121620; }")
        layout = QVBoxLayout(content); layout.setContentsMargins(2, 2, 12, 16); layout.setSpacing(9)
        content.setStyleSheet("""
            QWidget#usageContent { background: #121620; }
            QLabel#usageTitle { color: #FFFFFF; font-size: 21px; font-weight: 800; }
            QLabel#usageSubtitle { color: #B9C3D3; font-size: 12px; }
            QLabel#usageSection { color: #FFFFFF; font-size: 13px; font-weight: 800; margin-top: 8px; }
            QLabel#usageModeName { color: #F8FAFC; font-size: 12px; font-weight: 700; }
            QLabel#usageModeValue { color: #FFFFFF; font-size: 12px; font-weight: 800; }
            QLabel#usageEmpty { color: #C7D0DE; padding: 12px 2px; }
            QFrame#modeRow { background: #1A2231; border: 1px solid #303A4E; border-radius: 10px; }
            QProgressBar { background: #30394B; border: none; border-radius: 4px; height: 8px; }
            QProgressBar::chunk { background: #6D86F7; border-radius: 4px; }
        """)
        total = self.store.count(); counts = self.store.mode_counts()
        ai_count = sum(value for mode, value in counts.items() if mode.startswith("ai:") or mode in {"error", "quota_error"})
        gmail_count = counts.get("gmail_action", 0)
        title = QLabel("Usage"); title.setObjectName("usageTitle")
        subtitle = QLabel("A quick look at how you use the assistant"); subtitle.setObjectName("usageSubtitle")
        layout.addWidget(title); layout.addWidget(subtitle)
        quick_section = QLabel("Quick look"); quick_section.setObjectName("usageSection"); layout.addWidget(quick_section)
        cards = QHBoxLayout(); cards.setSpacing(10)
        cards.addWidget(StatCard("Interactions", f"{total:,}", "No activity recorded yet" if total == 0 else "Commands saved locally on this device"), 1)
        cards.addWidget(StatCard("AI responses", f"{ai_count:,}", "No AI requests recorded yet" if ai_count == 0 else "Requests sent through your configured AI providers"), 1)
        cards.addWidget(StatCard("Gmail actions", f"{gmail_count:,}", "No completed Gmail changes" if gmail_count == 0 else "Completed Gmail changes recorded"), 1)
        layout.addLayout(cards)
        section = QLabel("Activity by mode"); section.setObjectName("usageSection"); layout.addWidget(section)
        if not counts:
            empty = QLabel("No activity recorded yet. Your usage statistics will appear here as you use the assistant.")
            empty.setObjectName("usageEmpty"); empty.setWordWrap(True); layout.addWidget(empty)
        else:
            total_for_percent = max(sum(counts.values()), 1); max_count = max(counts.values())
            for mode, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])):
                percent = (count / total_for_percent) * 100
                row_frame = QFrame(); row_frame.setObjectName("modeRow"); row_frame.setMinimumHeight(52)
                row = QHBoxLayout(row_frame); row.setContentsMargins(12, 8, 12, 8); row.setSpacing(10)
                name = QLabel(self._mode_label(mode)); name.setObjectName("usageModeName"); name.setMinimumWidth(132); name.setWordWrap(True); name.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
                bar = QProgressBar(); bar.setRange(0, max_count); bar.setValue(count); bar.setTextVisible(False); bar.setMinimumWidth(70); bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                value = QLabel(f"{count:,}  ·  {percent:.0f}%"); value.setObjectName("usageModeValue"); value.setAlignment(Qt.AlignRight | Qt.AlignVCenter); value.setMinimumWidth(96); value.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred); value.setTextInteractionFlags(Qt.TextSelectableByMouse)
                row.addWidget(name); row.addWidget(bar, 1); row.addWidget(value); layout.addWidget(row_frame)
        layout.addStretch(1); self.scroll.setWidget(content)
