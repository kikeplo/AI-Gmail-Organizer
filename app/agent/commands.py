"""Command routing across Gmail, Windows, the AI provider, and local memory."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re

from app.ai.classifier import InboxClassifier
from app.gmail.action_service import GmailActionService
from app.gmail.client import GmailClient
from app.memory.store import MemoryStore
from app.windows.action_router import WindowsActionRouter


@dataclass(frozen=True)
class AgentResponse:
    text: str
    mode: str = "local"
    pending_action: object | None = None


class CommandAgent:
    """Route user requests to the appropriate application service."""

    def __init__(self, gmail: GmailClient | None = None, memory: MemoryStore | None = None) -> None:
        self.model = os.getenv("OPENAI_MODEL")
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.gmail = gmail or GmailClient()
        self.classifier = InboxClassifier()
        self.actions = GmailActionService(self.gmail)
        self.windows = WindowsActionRouter()
        self.memory = memory or MemoryStore()

    def respond(self, command: str) -> AgentResponse:
        command = command.strip()
        if not command:
            response = AgentResponse("Please enter a command.")
            self.memory.remember("", response.text, response.mode)
            return response

        lowered = command.casefold()
        remembered = self._handle_memory_query(lowered)
        if remembered is not None:
            self.memory.remember(command, remembered.text, remembered.mode)
            return remembered

        windows_response = self.windows.handle(command)
        if windows_response is not None:
            response = AgentResponse(windows_response.text, mode=windows_response.mode)
        elif self._looks_like_mutation(lowered):
            response = self._plan_mutation(command)
        elif self._looks_like_inbox_organization(lowered):
            response = self._handle_inbox_organization()
        elif self._looks_like_gmail_search(lowered):
            response = self._handle_gmail_search(command)
        elif not self.api_key or not self.model:
            response = AgentResponse(self._local_response(command), mode="demo")
        else:
            response = self._ask_ai(command)

        self.memory.remember(command, response.text, response.mode)
        return response

    def _ask_ai(self, command: str) -> AgentResponse:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            response = client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You are the desktop assistant for AI Gmail Organizer. "
                            "Gmail, Windows, and local memory capabilities are available. "
                            "Never claim that an external action occurred unless the application "
                            "explicitly reports success."
                        ),
                    },
                    {"role": "user", "content": command},
                ],
            )
            return AgentResponse(response.output_text, mode="openai")
        except Exception as exc:  # pragma: no cover
            message = str(exc)
            lowered = message.casefold()
            if "429" in lowered or "insufficient_quota" in lowered or "credit_balance_exhausted" in lowered:
                return AgentResponse(
                    "The AI provider is unavailable because the API account has no remaining credits.\n\n"
                    "Add API credits or switch to a different provider/configuration, then try again.",
                    mode="quota_error",
                )
            return AgentResponse("The AI provider could not be reached.\n\n" + message, mode="error")

    def _handle_memory_query(self, text: str) -> AgentResponse | None:
        if "history" in text or "remember" in text or "what did i ask" in text:
            interactions = self.memory.recent(8)
            if not interactions:
                return AgentResponse("I do not have any saved interaction history yet.", mode="memory")
            lines = ["Recent local memory:", ""]
            for item in interactions:
                lines.append(f"• {item.command or '(empty command)'}")
                lines.append(f"  {item.mode}: {item.response.splitlines()[0]}")
            return AgentResponse("\n".join(lines), mode="memory")
        if "usage" in text or "analytics" in text or "stats" in text:
            counts = self.memory.mode_counts()
            lines = [f"Local usage: {self.memory.count()} interaction(s)", ""]
            for mode, count in counts.items():
                lines.append(f"{mode}: {count}")
            return AgentResponse("\n".join(lines), mode="analytics")
        return None

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
        if "archive" in command.casefold():
            action = self.actions.plan_archive(ids)
        else:
            match = re.search(r"(?:label|move to)\s+['\"]?([^'\"]+)['\"]?$", command, flags=re.IGNORECASE)
            label_name = match.group(1).strip() if match else "Organized"
            action = self.actions.plan_label(ids, label_name)
        preview = ["Confirmation required", "", action.description, "", "Nothing has been changed yet.", "Confirm this action from the application before execution."]
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
            return AgentResponse(
                "Gmail is not connected yet.\n\n"
                f"Connection setup: {exc}\n\n"
                "Open Settings to configure Gmail, then run the command again.",
                mode="gmail_setup",
            )
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
        text = command.casefold()
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
        return (
            "Demo mode is active. Configure an AI provider for general AI commands, "
            "or use the supported Gmail, Windows, and memory commands.\n\n"
            f"Received: {command}"
        )
