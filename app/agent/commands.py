"""Command routing and AI provider integration for v0.2."""

from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class AgentResponse:
    """Structured response returned by the command agent."""

    text: str
    mode: str = "local"


class CommandAgent:
    """Small command agent that can use an OpenAI Responses API model when configured.

    Without an API key, it deliberately stays in local demo mode so the desktop UI
    remains usable without external credentials.
    """

    def __init__(self) -> None:
        self.model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
        self.api_key = os.getenv("OPENAI_API_KEY")

    def respond(self, command: str) -> AgentResponse:
        command = command.strip()
        if not command:
            return AgentResponse("Please enter a command.")

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
                            "For now, explain intended actions but do not claim that Gmail "
                            "or Windows actions were executed. Be concise and practical."
                        ),
                    },
                    {"role": "user", "content": command},
                ],
            )
            return AgentResponse(response.output_text, mode="openai")
        except Exception as exc:  # pragma: no cover - depends on external API
            return AgentResponse(
                f"The AI provider could not be reached.\n\n{exc}",
                mode="error",
            )

    @staticmethod
    def _local_response(command: str) -> str:
        """Provide useful demo responses without requiring an API key."""
        text = command.lower()

        if "gmail" in text or "email" in text or "inbox" in text:
            return (
                "Demo mode: Gmail is not connected yet.\n\n"
                "Next, this command will be translated into Gmail actions such as "
                "searching, grouping, labeling, archiving, or drafting emails."
            )

        return (
            "Demo mode is active. Add OPENAI_API_KEY to enable the AI model.\n\n"
            "The v0.2 command pipeline is ready for tool integrations."
        )
