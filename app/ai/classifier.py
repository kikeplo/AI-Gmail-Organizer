"""Inbox classification and summary services."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os

from app.gmail.client import GmailMessage

CATEGORIES = ("important", "work", "personal", "promotions", "newsletters", "other")


@dataclass(frozen=True)
class ClassifiedMessage:
    message: GmailMessage
    category: str
    confidence: float
    reason: str


class InboxClassifier:
    """Classify inbox messages with an OpenAI-compatible provider when configured."""

    def __init__(self) -> None:
        self.model = os.getenv("OPENAI_MODEL", "").strip()
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
        self.provider = os.getenv("AI_PROVIDER", "OpenAI-compatible").strip() or "OpenAI-compatible"

    def _client(self):
        from openai import OpenAI
        return OpenAI(api_key=self.api_key or "not-required", **({"base_url": self.base_url} if self.base_url else {}))

    def _resolve_model(self, client) -> str:
        if self.model:
            return self.model
        models = client.models.list()
        data = getattr(models, "data", None) or []
        if not data:
            raise RuntimeError("The provider did not return any models. Enter a model name in Settings, or use a provider that exposes /models.")
        model_id = getattr(data[0], "id", None)
        if not model_id:
            raise RuntimeError("The provider returned an invalid model list.")
        return str(model_id)

    def classify(self, messages: list[GmailMessage]) -> list[ClassifiedMessage]:
        if not messages:
            return []
        if self.api_key or self.base_url:
            try:
                return self._classify_with_ai(messages)
            except Exception:
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
        client = self._client()
        response = client.chat.completions.create(
            model=self._resolve_model(client),
            messages=[
                {"role": "system", "content": "Classify each email into exactly one category: important, work, personal, promotions, newsletters, or other. Return JSON only as an array of objects with id, category, confidence, reason."},
                {"role": "user", "content": json.dumps(payload)},
            ],
        )
        content = response.choices[0].message.content or "[]"
        results = {item["id"]: item for item in json.loads(content)}
        classified: list[ClassifiedMessage] = []
        for message in messages:
            item = results.get(message.id, {})
            category = item.get("category", "other")
            if category not in CATEGORIES:
                category = "other"
            classified.append(ClassifiedMessage(message, category, float(item.get("confidence", 0.5)), str(item.get("reason", "No explanation provided."))))
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
