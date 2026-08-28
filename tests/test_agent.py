from app.agent.commands import CommandAgent


def test_agent_handles_empty_command(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = CommandAgent().respond("")
    assert response.mode == "local"
    assert response.text == "Please enter a command."


def test_agent_gmail_demo_mode(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = CommandAgent().respond("Find my unread Gmail emails")
    assert response.mode == "demo"
    assert "Gmail is not connected yet" in response.text
