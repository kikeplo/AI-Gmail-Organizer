"""Bridge natural-language bulk Gmail requests into the existing confirmed-action flow."""

from __future__ import annotations

from types import MethodType
from urllib.parse import quote

from app.gmail.bulk import BulkGmailService


def install_bulk_gmail(agent) -> None:
    """Install bounded bulk Gmail command handling on a CommandAgent instance."""
    original_respond = agent.respond
    bulk = BulkGmailService(agent.gmail)

    def respond(self, command: str, on_status=None):
        if not bulk.is_bulk_archive_command(command):
            return original_respond(command, on_status=on_status)

        connection_error = self._connect()
        if connection_error is not None:
            return connection_error

        if on_status:
            on_status("Inspecting the desktop and opening Gmail…")
        try:
            # Best-effort visible Gmail navigation. The actual 500-message
            # matching stays on the Gmail API for accuracy and speed.
            try:
                self.windows.tools.launch_named_application("chrome")
                import time
                time.sleep(0.7)
                import pyautogui
                pyautogui.hotkey("ctrl", "l")
                pyautogui.write("https://mail.google.com", interval=0.01)
                pyautogui.press("enter")
                time.sleep(1.0)
            except Exception:
                pass

            plan = bulk.build_archive_plan(command)
            if not plan.messages:
                return type(self).respond.__globals__["AgentResponse"](bulk.describe(plan), mode="gmail")

            return type(self).respond.__globals__["AgentResponse"](
                bulk.describe(plan),
                mode="confirmation",
                pending_action=plan.action,
            )
        except Exception as exc:
            return type(self).respond.__globals__["AgentResponse"](
                f"Bulk Gmail analysis failed.\n\n{exc}", mode="gmail_error"
            )

    agent.respond = MethodType(respond, agent)
