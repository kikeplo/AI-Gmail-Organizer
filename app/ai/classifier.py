"""Inbox classification and summary services."""

from __future__ import annotations

from dataclasses import dataclass
import os

from app.ai.provider import AIProvider, AIProviderError
from app.gmail.client import GmailMessage

CATEGORIES = ("important", "work", "personal", "promotions", "newsletters", "other")


@dataclass(frozen=True)
class ClassifiedMessage:
    message: GmailMessage
    category: str
    confidence: float
    reason: str


class InboxClassifier:
    """Classify inbox messages through the configured AI provider."""

    def __init__(self) -> None:
        self.provider = AIProvider()

    def classify(self, messages: list[GmailMessage]) -> list[ClassifiedMessage]:
        if not messages:
            return []
        if self.provider.configured:
            try:
                return self._classify_with_ai(messages)
            except AIProviderError:
                return [self._local_classification(message) for message in messages]
        return [self._local_classification(message) for message in messages]

    def summarize(self, classified: list[ClassifiedMessage]) -> str:
        if not classified:
            return "No messages to summarize."
        counts = {category: 0 for category in CATEGORIES}
        for item in classified:
            counts[item.category] = counts.get(item.category, 0) + 1
        lines = [f"Inbox analysis — {len(classified)} messages", ""]
        for category in CATEGORIES:
            if counts[category]:
                lines.append(f"• {category.title()}: {counts[category]}")
        lines.extend(["", "Top messages:"])
        for index, item in enumerate(classified[:5], start=1):
            lines.append(f"{index}. [{item.category}] {item.message.subject}")
            lines.append(f"   {item.reason}")
        return "\n".join(lines)

    def _classify_with_ai(self, messages: list[GmailMessage]) -> list[ClassifiedMessage]:
        payload = [{"id": m.id, "sender": m.sender, "subject": m.subject, "snippet": m.snippet} for m in messages]
        system = (
            "Classify each email into exactly one category: important, work, personal, promotions, "
            "newsletters, or other. Return JSON only as an array of objects with id, category, confidence, reason."
        )
        items = self.provider.classify_json(payload, system)
        results = {item["id"]: item for item in items if isinstance(item, dict) and "id" in item}
        classified: list[ClassifiedMessage] = []
        for message in messages:
            item = results.get(message.id, {})
            category = item.get("category", "other")
            if category not in CATEGORIES:
                category = "other"
            try:
                confidence = float(item.get("confidence", 0.5))
            except (TypeError, ValueError):
                confidence = 0.5
            classified.append(ClassifiedMessage(message, category, confidence, str(item.get("reason", "No explanation provided."))))
        return classified

    @staticmethod
    def _local_classification(message: GmailMessage) -> ClassifiedMessage:
        text = f"{message.sender} {message.subject} {message.snippet}".lower()
        category = "other"
        reason = "No strong local signal detected."
        confidence = 0.45
        if any(word in text for word in ("unsubscribe", "newsletter", "weekly digest")):
            category, reason, confidence = "newsletters", "Contains newsletter-style language.", 0.9
        elif any(word in text for word in ("sale", "discount", "offer", "% off", "deal")):
            category, reason, confidence = "promotions", "Looks like a marketing or promotional email.", 0.85
        elif any(word in text for word in ("invoice", "meeting", "project", "deadline", "recruiter", "interview", "work")):
            category, reason, confidence = "work", "Contains work-related terms.", 0.78
        elif any(word in text for word in ("urgent", "action required", "important", "verify", "security")):
            category, reason, confidence = "important", "Contains urgency or action-required language.", 0.75
        elif any(word in text for word in ("family", "birthday", "vacation", "friend")):
            category, reason, confidence = "personal", "Contains personal-context terms.", 0.68
        return ClassifiedMessage(message, category, confidence, reason)
