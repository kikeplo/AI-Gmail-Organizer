"""Command routing for the AI Gmail Organizer v0.5."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re

from app.ai.classifier import InboxClassifier
from app.gmail.action_service import GmailActionService
from app.gmail.client import GmailClient


@dataclass(frozen=True)
class AgentResponse:
    text: str
    mode: str = "local"
    pending_action: object | None = None


class CommandAgent:
    """Route Gmail searches, classifications, and confirmed mutations."""

    def __init__(self, gmail: GmailClient | None = None) -> None:
        self.model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.gmail = gmail or GmailClient()
        self.classifier = InboxClassifier()
        self.actions = GmailActionService(self.gmail)

    def respond(self, command: str) -> AgentResponse:
        command = command.strip()
        if not command:
            return AgentResponse("Please enter a command.")

        lowered = command.lower()
        if self._looks_like_mutation(lowered):
            return self._plan_mutation(command)
        if self._looks_like_inbox_organization(lowered):
            return self._handle_inbox_organization()
        if self._looks_like_gmail_search(lowered):
            return self._handle_gmail_search(command)

        if not self.api_key:
            return AgentResponse(self._local_response(command), mode="demo")

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            response = client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You are the AI Gmail Organizer desktop assistant. "
                            "Gmail search, classification, label, and archive capabilities exist. "
                            "Never claim a Gmail mutation happened unless the application explicitly confirms it."
                        ),
                    },
                    {"role": "user", "content": command},
                ],
            )
            return AgentResponse(response.output_text, mode="openai")
        except Exception as exc:  # pragma: no cover
            return AgentResponse(f"The AI provider could not be reached.\n\n{exc}", mode="error")

    @staticmethod
    def _looks_like_inbox_organization(text: str) -> bool:
        return any(word in text for word in ("organize", "categorize", "categorise", "classify", "summarize", "analyse", "analyze")) and "inbox" in text

    @staticmethod
    def _looks_like_gmail_search(text: str) -> bool:
        return any(word in text for word in ("gmail", "email", "emails", "inbox")) and any(word in text for word in ("show", "find", "search", "list", "unread", "recent"))

    @staticmethod
    def _looks_like_mutation(text: str) -> bool:
        return any(word in text for word in ("archive", "label", "move to")) and any(word in text for word in ("email", "emails", "gmail", "message", "inbox"))

    def _plan_mutation(self, command: str) -> AgentResponse:
        connection_error = self._connect()
        if connection_error:
            return connection_error
        query = self._to_gmail_query(command)
        try:
            messages = self.gmail.list_messages(query=query, max_results=10)
        except Exception as exc:
            return AgentResponse(f"Gmail lookup failed.\n\n{exc}", mode="gmail_error")
        if not messages:
            return AgentResponse("No messages matched the request, so there is nothing to change.", mode="gmail")

        ids = [message.id for message in messages]
        if "archive" in command.lower():
            action = self.actions.plan_archive(ids)
        else:
            match = re.search(r"(?:label|move to)\s+['\"]?([^'\"]+)['\"]?$", command, flags=re.IGNORECASE)
            label_name = match.group(1).strip() if match else "Organized"
            action = self.actions.plan_label(ids, label_name)

        preview = [
            "⚠️ Confirmation required",
            "",
            action.description,
            "",
            "Nothing has been changed yet.",
            "Confirm this action from the application before execution.",
        ]
        return AgentResponse("\n".join(preview), mode="confirmation", pending_action=action)

    def confirm_action(self, action: object, confirmed: bool) -> AgentResponse:
        if not confirmed:
            return AgentResponse("Action cancelled. Your Gmail was not changed.", mode="cancelled")
        completed = self.actions.execute_confirmed(action, confirmed=True)  # type: ignore[arg-type]
        return AgentResponse(f"Done. {completed} Gmail message(s) were updated.", mode="gmail_action")

    def _connect(self) -> AgentResponse | None:
        if self.gmail.is_connected:
            return None
        try:
            self.gmail.connect()
        except Exception as exc:
            return AgentResponse("Gmail is not connected yet.\n\n" f"Connection setup: {exc}\n\n" "Once credentials.json is configured, run the command again.", mode="gmail_setup")
        return None

    def _handle_inbox_organization(self) -> AgentResponse:
        connection_error = self._connect()
        if connection_error:
            return connection_error
        try:
            messages = self.gmail.list_messages(query="", max_results=20)
            classified = self.classifier.classify(messages)
            return AgentResponse(self.classifier.summarize(classified), mode="classification")
        except Exception as exc:
            return AgentResponse(f"Inbox analysis failed.\n\n{exc}", mode="gmail_error")

    def _handle_gmail_search(self, command: str) -> AgentResponse:
        connection_error = self._connect()
        if connection_error:
            return connection_error
        query = self._to_gmail_query(command)
        try:
            messages = self.gmail.list_messages(query=query, max_results=10)
        except Exception as exc:
            return AgentResponse(f"Gmail search failed.\n\n{exc}", mode="gmail_error")
        if not messages:
            return AgentResponse("No matching Gmail messages were found.", mode="gmail")
        lines = [f"Found {len(messages)} message(s):", ""]
        for index, message in enumerate(messages, start=1):
            lines.extend((f"{index}. {message.subject}", f"   From: {message.sender}", f"   {message.snippet}"))
        return AgentResponse("\n".join(lines), mode="gmail")

    @staticmethod
    def _to_gmail_query(command: str) -> str:
        text = command.lower()
        queries: list[str] = []
        if "unread" in text:
            queries.append("is:unread")
        if "starred" in text:
            queries.append("is:starred")
        sender = re.search(r"from\s+([\w.+-]+@[\w.-]+)", text)
        if sender:
            queries.append(f"from:{sender.group(1)}")
        return " ".join(queries)

    @staticmethod
    def _local_response(command: str) -> str:
        return "Demo mode is active. Add OPENAI_API_KEY for general AI commands, or configure Gmail OAuth to search and organize your inbox.\n\nReceived: " + command
