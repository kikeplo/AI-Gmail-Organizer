"""Natural-language routing for safe Windows desktop actions in v0.6."""

from __future__ import annotations

from dataclasses import dataclass

from app.windows.tools import ActiveWindow, WindowsTools


@dataclass(frozen=True)
class WindowActionResponse:
    text: str
    mode: str = "windows"


class WindowsActionRouter:
    """Translate a small set of explicit desktop intents into Windows tools."""

    def __init__(self, tools: WindowsTools | None = None) -> None:
        self.tools = tools or WindowsTools()

    def handle(self, command: str) -> WindowActionResponse | None:
        text = command.casefold().strip()
        if not self._is_windows_intent(text):
            return None

        try:
            if any(term in text for term in ("what window", "active window", "focused window", "which window")):
                window = self.tools.get_active_window()
                return WindowActionResponse(self._describe_active_window(window))

            if "minimize" in text and "window" in text:
                self.tools.minimize_active_window()
                return WindowActionResponse("The active window was minimized.")

            if "maximize" in text and "window" in text:
                self.tools.maximize_active_window()
                return WindowActionResponse("The active window was maximized.")

            if ("restore" in text or "unmaximize" in text) and "window" in text:
                self.tools.restore_active_window()
                return WindowActionResponse("The active window was restored.")

            return WindowActionResponse(
                "Windows tools are available for the active window. Try: "
                "‘What window is active?’, ‘Minimize the active window’, "
                "or ‘Maximize the active window’."
            )
        except OSError as exc:
            return WindowActionResponse(str(exc), mode="windows_unavailable")
        except Exception as exc:
            return WindowActionResponse(f"Windows action failed.\n\n{exc}", mode="windows_error")

    @staticmethod
    def _is_windows_intent(text: str) -> bool:
        return (
            "window" in text
            or "desktop" in text
            or "screen" in text
        ) and any(
            term in text
            for term in (
                "active",
                "focused",
                "minimize",
                "maximize",
                "restore",
                "what window",
                "which window",
            )
        )

    @staticmethod
    def _describe_active_window(window: ActiveWindow) -> str:
        lines = [f"Active window: {window.title}"]
        if window.process_id is not None:
            lines.append(f"Process ID: {window.process_id}")
        if window.executable:
            lines.append(f"Executable: {window.executable}")
        return "\n".join(lines)
