"""Command routing for the AI Gmail Organizer."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re

from app.gmail.client import GmailClient


@dataclass(frozen=True)
class AgentResponse:
    """Structured response returned by the command agent."""

    text: str
    mode: str = "local"


class CommandAgent:
    """Route safe read-only Gmail commands and optional AI requests."""

    def __init__(self, gmail: GmailClient | None = None) -> None:
        self.model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.gmail = gmail or GmailClient()

    def respond(self, command: str) -> AgentResponse:
        command = command.strip()
        if not command:
            return AgentResponse("Please enter a command.")

        lowered = command.lower()
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
                            "Gmail read-only search is available. Do not claim external "
                            "actions were executed unless the application explicitly reports them."
                        ),
                    },
                    {"role": "user", "content": command},
                ],
            )
            return AgentResponse(response.output_text, mode="openai")
        except Exception as exc:  # pragma: no cover - external service dependent
            return AgentResponse(
                f"The AI provider could not be reached.\n\n{exc}", mode="error"
            )

    @staticmethod
    def _looks_like_gmail_search(text: str) -> bool:
        return any(word in text for word in ("gmail", "email", "emails", "inbox")) and any(
            word in text for word in ("show", "find", "search", "list", "unread", "recent")
        )

    def _handle_gmail_search(self, command: str) -> AgentResponse:
        if not self.gmail.is_connected:
            try:
                self.gmail.connect()
            except Exception as exc:
                return AgentResponse(
                    "Gmail is not connected yet.\n\n"
                    f"Connection setup: {exc}\n\n"
                    "Once credentials.json is configured, run the command again.",
                    mode="gmail_setup",
                )

        query = self._to_gmail_query(command)
        try:
            messages = self.gmail.list_messages(query=query, max_results=10)
        except Exception as exc:
            return AgentResponse(f"Gmail search failed.\n\n{exc}", mode="gmail_error")

        if not messages:
            return AgentResponse("No matching Gmail messages were found.", mode="gmail")

        lines = [f"Found {len(messages)} message(s):", ""]
        for index, message in enumerate(messages, start=1):
            lines.append(f"{index}. {message.subject}")
            lines.append(f"   From: {message.sender}")
            lines.append(f"   {message.snippet}")
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
        return (
            "Demo mode is active. Add OPENAI_API_KEY for general AI commands, "
            "or configure Gmail OAuth to search your inbox.\n\n"
            f"Received: {command}"
        )
