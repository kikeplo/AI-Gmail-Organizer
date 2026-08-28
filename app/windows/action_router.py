"""Natural-language routing for Windows desktop actions."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
import subprocess

from app.windows.tools import ActiveWindow, WindowsTools
from app.windows.ui_automation import UIAutomationError, WindowsUIAutomation


@dataclass(frozen=True)
class WindowActionResponse:
    text: str
    mode: str = "windows"


class WindowsActionRouter:
    """Translate desktop requests into semantic UI automation, app launch, or low-level input."""

    APP_ALIASES = {
        "microsoft teams": "msteams:",
        "teams": "msteams:",
        "calculator": "calculator:",
        "calc": "calculator:",
    }

    def __init__(self, tools: WindowsTools | None = None, ui: WindowsUIAutomation | None = None) -> None:
        self.tools = tools or WindowsTools()
        self.ui = ui or WindowsUIAutomation()

    def handle(self, command: str) -> WindowActionResponse | None:
        text = command.casefold().strip()
        if not self._is_windows_intent(text):
            return None
        try:
            app_name = self._app_to_open(command)
            if app_name:
                try:
                    self._launch_known_app(app_name)
                    return WindowActionResponse(f"Opening {app_name}.", mode="windows_app_launch")
                except Exception as launch_error:
                    # Continue to semantic UI automation if the app protocol could not be launched.
                    try:
                        semantic = self._semantic_click_target(command)
                        if semantic:
                            element = self.ui.click(semantic)
                            return WindowActionResponse(f"Opened '{element.name}' using Windows UI Automation.", mode="windows_ui_action")
                    except Exception:
                        pass
                    raise launch_error

            try:
                semantic = self._semantic_click_target(command)
                if semantic:
                    element = self.ui.click(semantic)
                    return WindowActionResponse(f"Clicked '{element.name}' using Windows UI Automation.", mode="windows_ui_action")
            except UIAutomationError as ui_error:
                # pywinauto may be unavailable in an unpacked/incomplete build. Continue to
                # deterministic low-level actions instead of turning every command into an error.
                if any(term in text for term in ("click", "double click", "double-click", "right click", "right-click", "type ", "press ", "hotkey", "shortcut", "scroll")):
                    pass
                else:
                    return WindowActionResponse(
                        f"Semantic Windows controls are unavailable ({ui_error}). I can still use direct desktop controls or visual automation.",
                        mode="windows_ui_unavailable",
                    )

            if any(term in text for term in ("what window", "active window", "focused window", "which window")):
                return WindowActionResponse(self._describe_active_window(self.tools.get_active_window()))
            if "double click" in text or "double-click" in text:
                point = self._coordinates(text)
                self.tools.double_click(*point) if point else self.tools.double_click()
                return WindowActionResponse("Double-click completed.", mode="windows_action")
            if "right click" in text or "right-click" in text:
                point = self._coordinates(text)
                self.tools.click(*point, button="right") if point else self.tools.click(button="right")
                return WindowActionResponse("Right-click completed.", mode="windows_action")
            if "click" in text:
                point = self._coordinates(text)
                self.tools.click(*point) if point else self.tools.click()
                return WindowActionResponse("Click completed.", mode="windows_action")
            if "type " in text or text.startswith("type"):
                match = re.search(r"\btype\s+(?:the following\s*:\s*)?[\"']?(.*?)[\"']?$", command, re.IGNORECASE)
                if match:
                    self.tools.type_text(match.group(1))
                    return WindowActionResponse("Text entered.", mode="windows_action")
            if "press " in text:
                key = text.split("press ", 1)[1].strip().strip("\"'")
                self.tools.press(key)
                return WindowActionResponse(f"Pressed {key}.", mode="windows_action")
            if "hotkey" in text or "shortcut" in text:
                match = re.search(r"(?:hotkey|shortcut)\s+(.+)$", text)
                if match:
                    keys = [part.strip() for part in re.split(r"[+, ]+", match.group(1)) if part.strip()]
                    self.tools.hotkey(*keys)
                    return WindowActionResponse("Keyboard shortcut completed.", mode="windows_action")
            if "scroll" in text:
                amount = -5 if any(term in text for term in ("down", "bottom")) else 5
                if re.search(r"\bup\b", text): amount = 5
                self.tools.scroll(amount)
                return WindowActionResponse("Scrolled the active window.", mode="windows_action")
            if "minimize" in text and "window" in text:
                self.tools.minimize_active_window()
                return WindowActionResponse("The active window was minimized.", mode="windows_action")
            if "maximize" in text and "window" in text:
                self.tools.maximize_active_window()
                return WindowActionResponse("The active window was maximized.", mode="windows_action")
            if ("restore" in text or "unmaximize" in text) and "window" in text:
                self.tools.restore_active_window()
                return WindowActionResponse("The active window was restored.", mode="windows_action")
            return WindowActionResponse("Desktop control is available. You can ask me to click, double-click, type, press a key, use a shortcut, scroll, or control the active window.")
        except OSError as exc:
            return WindowActionResponse(str(exc), mode="windows_unavailable")
        except Exception as exc:
            return WindowActionResponse(f"Desktop action failed.\n\n{exc}", mode="windows_error")

    @classmethod
    def _app_to_open(cls, command: str) -> str | None:
        text = command.casefold().strip()
        match = re.match(r"(?:open|launch|start|run)\s+(?:the\s+)?(.+?)(?:\s+app|\s+application)?$", text)
        if not match:
            return None
        candidate = re.sub(r"[^a-z0-9 ]+", " ", match.group(1)).strip()
        return candidate if candidate in cls.APP_ALIASES else None

    @classmethod
    def _launch_known_app(cls, app_name: str) -> None:
        if os.name != "nt":
            raise OSError("Windows app launching is only available on Windows.")
        protocol = cls.APP_ALIASES[app_name]
        os.startfile(protocol)

    @staticmethod
    def _semantic_click_target(command: str) -> str | None:
        text = command.strip()
        match = re.search(r"(?:click|press|select|open)\s+(?:the\s+)?(?:button|tab|link|menu item|item)?\s*[\"']?([^\"']+?)[\"']?$", text, re.IGNORECASE)
        if not match:
            return None
        target = match.group(1).strip()
        if not target or re.search(r"\d+\s*[, ]\s*\d+", target):
            return None
        return target

    @staticmethod
    def _coordinates(text: str) -> tuple[int, int] | None:
        match = re.search(r"(?:at|coordinates?\s*[:=]?)\s*(\d+)\s*[, ]\s*(\d+)", text)
        return (int(match.group(1)), int(match.group(2))) if match else None

    @staticmethod
    def _is_windows_intent(text: str) -> bool:
        actions = ("active", "focused", "minimize", "maximize", "restore", "click", "double click", "double-click", "right click", "right-click", "type ", "press ", "hotkey", "shortcut", "scroll", "select", "open ", "launch ", "start ", "run ")
        return ("window" in text or "desktop" in text or "screen" in text or any(term in text for term in actions)) and any(term in text for term in actions)

    @staticmethod
    def _describe_active_window(window: ActiveWindow) -> str:
        lines = [f"Active window: {window.title}"]
        if window.process_id is not None: lines.append(f"Process ID: {window.process_id}")
        if window.executable: lines.append(f"Executable: {window.executable}")
        return "\n".join(lines)
