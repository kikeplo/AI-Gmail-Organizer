"""Background worker for operations that may involve network or slow I/O."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from app.agent.commands import AgentResponse, CommandAgent


class CommandWorker(QObject):
    """Run an agent command outside the Qt GUI thread and report progress."""

    finished = Signal(object)
    failed = Signal(str)
    status = Signal(str)

    def __init__(self, agent: CommandAgent, command: str) -> None:
        super().__init__()
        self.agent = agent
        self.command = command

    @Slot()
    def run(self) -> None:
        try:
            response: AgentResponse = self.agent.respond(self.command, on_status=self.status.emit)
            self.finished.emit(response)
        except Exception as exc:  # pragma: no cover
            self.failed.emit(str(exc))
