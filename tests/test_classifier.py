from app.ai.classifier import InboxClassifier
from app.gmail.client import GmailMessage


def test_local_classifier_detects_newsletters(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    message = GmailMessage("1", "t1", "news@example.com", "Weekly newsletter", "Unsubscribe here")
    result = InboxClassifier().classify([message])[0]
    assert result.category == "newsletters"
    assert result.confidence > 0.8


def test_summary_counts_categories(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    messages = [
        GmailMessage("1", "t1", "boss@example.com", "Project meeting", "Deadline tomorrow"),
        GmailMessage("2", "t2", "shop@example.com", "50% off", "Sale today"),
    ]
    classified = InboxClassifier().classify(messages)
    summary = InboxClassifier().summarize(classified)
    assert "Work: 1" in summary
    assert "Promotions: 1" in summary
