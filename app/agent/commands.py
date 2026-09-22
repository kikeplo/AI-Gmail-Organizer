"""Command routing across Gmail, Windows, browser, AI, local memory, and vision."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
import threading

from app.ai.provider import AIProvider, AIProviderError
from app.ai.router import SmartAIRouter
from app.ai.local_engine import LocalAIEngine, LocalAIError
from app.browser.playwright_controller import BrowserAutomationError, PlaywrightController
from app.gmail.action_service import GmailActionService
from app.gmail.client import GmailClient
from app.agent.procedures import ProcedureStore
from app.agent.task_planner import TaskPlanner
from app.memory.knowledge import LocalKnowledge
from app.memory.retrieval import LocalRetriever
from app.memory.store import MemoryStore
from app.windows.action_router import WindowsActionRouter
from app.vision.agent import VisionAgent, VisionAgentError


@dataclass(frozen=True)
class AgentResponse:
    text: str
    mode: str = "local"
    pending_action: object | None = None


class CommandCancelled(RuntimeError):
    """Raised internally when the user stops the active command."""


class CommandAgent:
    """Route requests across structured tools, browser/desktop automation, AI, memory, and tasks."""

    def __init__(self, gmail: GmailClient | None = None, memory: MemoryStore | None = None) -> None:
        self.ai = AIProvider()
        self.local_ai = LocalAIEngine()
        self.ai_router = SmartAIRouter()
        self.gmail = gmail or GmailClient()
        self.actions = GmailActionService(self.gmail)
        self.windows = WindowsActionRouter()
        self.browser = PlaywrightController()
        self.memory = memory or MemoryStore()
        self.knowledge = LocalKnowledge(self.memory.db_path)
        self.retriever = LocalRetriever(self.memory.db_path)
        self.procedures = ProcedureStore(self.memory.db_path)
        self.tasks = TaskPlanner(self.memory.db_path)
        self.vision = VisionAgent(self.ai_router, self.windows.tools)
        self._running_task = False
        self._cancel_event = threading.Event()

    def begin_command(self) -> None:
        self._cancel_event.clear()
        self.ai_router.begin_operation()

    def stop_task(self) -> None:
        self._running_task = False
        self._cancel_event.set()
        self.vision.stop()
        self.ai_router.cancel()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def _check_cancelled(self) -> None:
        if self._cancel_event.is_set():
            raise CommandCancelled("Command stopped by user.")

    def pause_task(self) -> None:
        self.vision.pause()

    def resume_task(self) -> None:
        self.vision.resume()

    def respond(self, command: str, on_status=None) -> AgentResponse:
        self._check_cancelled()
        command = command.strip()
        if not command:
            response = AgentResponse("Please enter a command.")
            self.memory.remember("", response.text, response.mode)
            return response

        lowered = command.casefold()
        task_response = self._handle_task_commands(command, lowered, on_status)
        if task_response is not None:
            self.memory.remember(command, task_response.text, task_response.mode)