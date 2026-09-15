"""Background worker for operations that may involve network or slow I/O."""

from __future__ import annotations

import threading
import time

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
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None

    def _start_heartbeat(self) -> None:
        started = time.monotonic()

        def heartbeat() -> None:
            last_second = -1
            while not self._heartbeat_stop.wait(0.8):
                elapsed = int(time.monotonic() - started)
                if elapsed != last_second:
                    last_second = elapsed
                    self.status.emit(f"Working… {elapsed}s elapsed")

        self._heartbeat_thread = threading.Thread(target=heartbeat, name="command-heartbeat", daemon=True)
        self._heartbeat_thread.start()

    def _stop_heartbeat(self) -> None:
        self._heartbeat_stop.set()
        thread = self._heartbeat_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=0.5)
        self._heartbeat_thread = None

    @Slot()
    def run(self) -> None:
        self._start_heartbeat()
        try:
            self.status.emit("Starting…")
            response: AgentResponse = self.agent.respond(self.command, on_status=self.status.emit)
            self.finished.emit(response)
        except Exception as exc:  # pragma: no cover
            self.failed.emit(str(exc))
        finally:
            self._stop_heartbeat()
