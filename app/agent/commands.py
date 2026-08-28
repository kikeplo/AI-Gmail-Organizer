"""Command routing across Gmail, Windows, vision, AI, and local memory."""

from __future__ import annotations

from dataclasses import dataclass
import re

from app.ai.classifier import AIProvider, AIProviderError
from app.gmail.action_service import GmailActionService
from app.gmail.client import GmailClient
from app.memory.store import MemoryStore
from app.windows.action_router import WindowsActionRouter
from app.windows.computer_use import ComputerUseError, VisionComputerUse


@dataclass(frozen=True)
class AgentResponse:
    text: str
    mode: str = "local"
    pending_action: object | None = None


class CommandAgent:
    """Route user requests to application services and visual desktop control."""

    def __init__(self, gmail: GmailClient | None = None, memory: MemoryStore | None = None) -> None:
        self.ai = AIProvider()
        self.gmail = gmail or GmailClient()
        self.actions = GmailActionService(self.gmail)
        self.windows = WindowsActionRouter()
        self.vision = VisionComputerUse(self.ai)
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

        if self._looks_like_visual_task(lowered):
            response = self._handle_visual_task(command)
        else:
            windows_response = self.windows.handle(command)
            if windows_response is not None:
                response = AgentResponse(windows_response.text, mode=windows_response.mode)
            elif self._looks_like_mutation(lowered):
                response = self._plan_mutation(command)
            elif self._looks_like_inbox_organization(lowered):
                response = self._handle_inbox_organization()
            elif self._looks_like_gmail_search(lowered):
                response = self._handle_gmail_search(command)
            elif not self.ai.configured:
                response = AgentResponse(self._local_response(command), mode="demo")
            else:
                response = self._ask_ai(command)

        self.memory.remember(command, response.text, response.mode)
        return response

    def _handle_visual_task(self, command: str) -> AgentResponse:
        try:
            result = self.vision.run(command)
            return AgentResponse(result, mode="computer_use")
        except (ComputerUseError, AIProviderError) as exc:
            return AgentResponse(f"Visual desktop control could not complete the request.\n\n{exc}", mode="computer_use_error")
        except Exception as exc:  # pragma: no cover
            return AgentResponse(f"Visual desktop control failed.\n\n{exc}", mode="computer_use_error")

    @staticmethod
    def _looks_like_visual_task(text: str) -> bool:
        visual_terms = (
            "click", "double click", "right click", "move the mouse", "move mouse", "type into",
            "type in", "press a key", "press enter", "scroll", "open the tab", "go to the tab",
            "navigate", "on screen", "on the screen", "look at my screen", "use the mouse",
            "use my mouse", "control my computer", "control the computer", "open gmail", "go to gmail",
            "open chrome", "open browser", "find on screen", "screen and click", "visually",
        )
        return any(term in text for term in visual_terms)

    def _ask_ai(self, command: str) -> AgentResponse:
        try:
            content = self.ai.chat(
                command,
                "You are the desktop assistant for AI Gmail Organizer. Gmail, Windows, visual computer control, and local memory capabilities are available. Never claim that an external action occurred unless the application explicitly reports success.",
            )
            return AgentResponse(content, mode=f"ai:{self.ai.provider or self.ai._protocol()}")
        except AIProviderError as exc:
            return AgentResponse(f"The configured AI provider could not complete the request.\n\n{exc}\n\nCheck the API key and base URL and try again.", mode="error")
        except Exception as exc:
            return AgentResponse(f"AI request failed.\n\n{exc}", mode="error")

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
            return AgentResponse("Gmail is not connected yet.\n\nConnection setup: " + str(exc) + "\n\nOpen Settings to configure Gmail, then run the command again.", mode="gmail_setup")
        return None

    def _handle_inbox_organization(self) -> AgentResponse:
        connection_error = self._connect()
        if connection_error:
            return connection_error
        try:
            messages = self.gmail.list_messages(query="", max_results=20)
            from app.ai.classifier import InboxClassifier
            classified = InboxClassifier().classify(messages)
            return AgentResponse(InboxClassifier().summarize(classified), mode="classification")
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
        return "Demo mode is active. Configure an AI provider for general AI commands, or use the supported Gmail, Windows, and memory commands.\n\nReceived: " + command
