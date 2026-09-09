"""Bridge natural-language bulk Gmail requests into the existing confirmed-action flow."""

from __future__ import annotations

import os
from types import MethodType

from app.gmail.bulk import BulkGmailService


def install_bulk_gmail(agent) -> None:
    """Install bounded bulk Gmail command handling on a CommandAgent instance."""
    original_respond = agent.respond
    original_confirm = agent.confirm_action
    bulk = BulkGmailService(agent.gmail)

    def respond(self, command: str, on_status=None):
        if not bulk.is_bulk_archive_command(command):
            return original_respond(command, on_status=on_status)

        connection_error = self._connect()
        if connection_error is not None:
            return connection_error

        if on_status:
            on_status("Checking recent inbox messages…")
        try:
            # Gmail API analysis is the source of truth. Opening Chrome is
            # optional because it adds noticeable startup/navigation latency.
            if os.getenv("OPEN_GMAIL_FOR_BULK", "0").strip().lower() in {"1", "true", "yes"}:
                try:
                    self.windows.tools.launch_named_application("chrome")
                    import pyautogui
                    pyautogui.hotkey("ctrl", "l")
                    pyautogui.write("https://mail.google.com", interval=0.0)
                    pyautogui.press("enter")
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

    def confirm_action(self, action: object, confirmed: bool):
        result = original_confirm(action, confirmed)
        if confirmed and getattr(action, "action", None) == "archive" and getattr(action, "message_ids", None):
            try:
                remaining_ids = set(self.gmail.list_message_ids(query="in:inbox", max_results=500))
                archived = sum(1 for message_id in action.message_ids if message_id not in remaining_ids)
                total = len(action.message_ids)
                if archived == total:
                    return type(self).respond.__globals__["AgentResponse"](
                        f"Done. {archived} message(s) were archived and verified as removed from the inbox.",
                        mode="gmail_action",
                    )
                return type(self).respond.__globals__["AgentResponse"](
                    f"Archive finished for {archived} of {total} message(s); the result could not be fully verified.",
                    mode="gmail_action",
                )
            except Exception:
                return result
        return result

    agent.respond = MethodType(respond, agent)
    agent.confirm_action = MethodType(confirm_action, agent)
