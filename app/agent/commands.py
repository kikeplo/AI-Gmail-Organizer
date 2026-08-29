"""Command routing across Gmail, Windows, browser, AI, local memory, and vision."""

from __future__ import annotations

from dataclasses import dataclass
import re

from app.ai.provider import AIProviderError
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


class CommandAgent:
    """Route requests across structured tools, browser/desktop automation, AI, memory, and tasks."""

    def __init__(self, gmail: GmailClient | None = None, memory: MemoryStore | None = None) -> None:
        self.ai_router = SmartAIRouter()
        self.local_ai = LocalAIEngine()
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

    @property
    def ai(self):
        return self.ai_router.cloud

    def stop_task(self) -> None:
        self._running_task = False
        self.vision.stop()

    def pause_task(self) -> None:
        self.vision.pause()

    def resume_task(self) -> None:
        self.vision.resume()

    def respond(self, command: str, on_status=None) -> AgentResponse:
        command = command.strip()
        if not command:
            response = AgentResponse("Please enter a command.")
            self.memory.remember("", response.text, response.mode)
            return response
        lowered = command.casefold()
        task_response = self._handle_task_commands(command, lowered, on_status)
        if task_response is not None:
            self.memory.remember(command, task_response.text, task_response.mode)
            return task_response
        procedure_response = self._handle_procedure_commands(command, lowered, on_status)
        if procedure_response is not None:
            self.memory.remember(command, procedure_response.text, procedure_response.mode)
            return procedure_response
        knowledge_response = self._handle_knowledge(command, lowered)
        if knowledge_response is not None:
            self.memory.remember(command, knowledge_response.text, knowledge_response.mode)
            return knowledge_response
        remembered = self._handle_memory_query(lowered)
        if remembered is not None:
            self.memory.remember(command, remembered.text, remembered.mode)
            return remembered
        if lowered in {"ai status", "provider status", "ai providers", "ai health"}:
            return AgentResponse(self._format_provider_status(), mode="ai_status")
        matching = self.procedures.search(command, limit=1)
        if matching and matching[0].score >= 1.2 and matching[0].steps and any(term in lowered for term in ("do", "run", "open", "navigate", "repeat", "again")):
            if on_status:
                on_status(f"Reusing learned procedure: {matching[0].name}")
            return AgentResponse(f"I found a learned procedure for this request: {matching[0].name}.\n\nThe stored procedure is available as reusable guidance; each action is still verified before execution.", mode="procedure_found")
        if self._looks_like_browser_task(lowered):
            try:
                response = self._handle_browser(command)
            except BrowserAutomationError as exc:
                response = AgentResponse(f"Browser automation is unavailable.\n\n{exc}\n\nI can fall back to Windows/vision control when appropriate.", mode="browser_error")
            except Exception as exc:
                response = AgentResponse(f"Browser task failed.\n\n{exc}", mode="browser_error")
        elif self._looks_like_visual_task(lowered):
            try:
                result = self.vision.run(command, progress=on_status)
                response = AgentResponse(result, mode="vision")
                if not result.lower().startswith("task stopped") and not result.lower().startswith("i paused") and getattr(self.vision, "last_steps", None):
                    name = self._procedure_name(command)
                    procedure_id = self.procedures.save(name, command, self.vision.last_steps)
                    self.procedures.record_result(procedure_id, True)
                    response = AgentResponse(result + f"\n\nSaved this successful workflow as '{name}' for future reuse.", mode="vision_learned")
            except VisionAgentError as exc:
                response = AgentResponse(str(exc), mode="vision_error")
            except Exception as exc:
                response = AgentResponse(f"Visual task failed.\n\n{exc}", mode="vision_error")
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
            elif self._should_use_local_ai(lowered) and self.local_ai.available():
                response = self._ask_local_ai(command)
            elif not self.ai.configured:
                response = self._local_response_from_search(command)
            else:
                response = self._ask_ai(command)
        self.memory.remember(command, response.text, response.mode)
        return response
