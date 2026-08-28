from app.agent.commands import CommandAgent
from app.gmail.client import GmailClient


def test_gmail_query_from_unread_sender():
    query = CommandAgent._to_gmail_query("Find unread emails from recruiter@example.com")
    assert query == "is:unread from:recruiter@example.com"


def test_gmail_query_starred():
    query = CommandAgent._to_gmail_query("Show my starred emails")
    assert query == "is:starred"


def test_gmail_client_starts_disconnected():
    client = GmailClient()
    assert client.is_connected is False
