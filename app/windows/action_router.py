"""Natural-language routing for Windows desktop actions."""

from __future__ import annotations

from dataclasses import dataclass
import re

from app.windows.tools import ActiveWindow, WindowsTools
from app.windows.ui_automation import UIAutomationError, WindowsUIAutomation


@dataclass(frozen=True)
class WindowActionResponse:
    text: str
    mode: str = "windows"


class WindowsActionRouter:
    """Translate natural-language desktop requests into safe Windows actions."""

    def __init__(self, tools: WindowsTools | None = None, ui: WindowsUIAutomation | None = None) -> None:
        self.tools = tools or WindowsTools()
        self.ui = ui or WindowsUIAutomation()

    def set_own_window(self, hwnd: int | None) -> None:
        self.tools.set_own_window(hwnd)

    def handle(self, command: str) -> WindowActionResponse | None:
        text = command.casefold().strip()
        if not self._is_windows_intent(text):
            return None
        try:
            if any(term in text for term in ("what window", "active window", "focused window", "which window")):
                return WindowActionResponse(self._describe_active_window(self.tools.get_last_external_window()), mode="windows_active_window")

            if self._is_start_button_request(text):
                self.tools.hotkey("winleft")
                return WindowActionResponse("Opened the Windows Start menu.", mode="windows_start")

            file_target = self._file_request(command)
            if file_target:
                target, location = file_target
                message = self.tools.open_file_or_folder(target, location)
                return WindowActionResponse(message, mode="windows_file_open")

            desktop_app, as_admin = self._desktop_app_request(command)
            if desktop_app:
                message = self.tools.launch_named_application(desktop_app, as_admin=as_admin)
                return WindowActionResponse(message, mode="windows_app_launch_admin" if as_admin else "windows_app_launch")

            try:
                semantic = self._semantic_click_target(command)
                if semantic:
                    element = self.ui.click(semantic)
                    return WindowActionResponse(f"Clicked '{element.name}' using Windows UI Automation.", mode="windows_ui_action")
            except UIAutomationError:
                pass

            if "double click" in text or "double-click" in text:
                point = self._coordinates(text); self.tools.double_click(*point) if point else self.tools.double_click(); return WindowActionResponse("Double-click completed.", mode="windows_action")
            if "right click" in text or "right-click" in text:
                point = self._coordinates(text); self.tools.click(*point, button="right") if point else self.tools.click(button="right"); return WindowActionResponse("Right-click completed.", mode="windows_action")
            if "click" in text:
                point = self._coordinates(text); self.tools.click(*point) if point else self.tools.click(); return WindowActionResponse("Click completed.", mode="windows_action")
            if "type " in text or text.startswith("type"):
                match = re.search(r"\btype\s+(?:the following\s*:\s*)?[\"']?(.*?)[\"']?$", command, re.IGNORECASE)
                if match: self.tools.type_text(match.group(1)); return WindowActionResponse("Text entered.", mode="windows_action")
            if "press " in text:
                key = text.split("press ", 1)[1].strip().strip("\"'"); self.tools.press(key); return WindowActionResponse(f"Pressed {key}.", mode="windows_action")
            if "hotkey" in text or "shortcut" in text:
                match = re.search(r"(?:hotkey|shortcut)\s+(.+)$", text)
                if match:
                    keys = [part.strip() for part in re.split(r"[+, ]+", match.group(1)) if part.strip()]; self.tools.hotkey(*keys); return WindowActionResponse("Keyboard shortcut completed.", mode="windows_action")
            if "scroll" in text:
                amount = -5 if any(term in text for term in ("down", "bottom")) else 5
                if re.search(r"\bup\b", text): amount = 5
                self.tools.scroll(amount); return WindowActionResponse("Scrolled the active window.", mode="windows_action")
            if "minimize" in text and "window" in text: self.tools.minimize_active_window(); return WindowActionResponse("The active window was minimized.", mode="windows_action")
            if "maximize" in text and "window" in text: self.tools.maximize_active_window(); return WindowActionResponse("The active window was maximized.", mode="windows_action")
            if ("restore" in text or "unmaximize" in text) and "window" in text: self.tools.restore_active_window(); return WindowActionResponse("The active window was restored.", mode="windows_action")
            return WindowActionResponse("I couldn't map that desktop request to a safe direct action yet. I can work with apps, files, folders, windows, mouse, keyboard, and shortcuts.")
        except OSError as exc:
            return WindowActionResponse(str(exc), mode="windows_unavailable")
        except Exception as exc:
            return WindowActionResponse(f"Desktop action failed.\n\n{exc}", mode="windows_error")

    @staticmethod
    def _file_request(command: str) -> tuple[str, str] | None:
        """Recognize natural-language file/folder requests, including latest files."""
        text = command.strip()
        lowered = text.casefold()
        verb = re.match(r"^\s*(?:open|launch|start|run|double[- ]click|show)\s+(.+?)\s*$", text, re.IGNORECASE)
        if not verb:
            return None

        body = verb.group(1).strip()
        original_body = body

        # Pull an explicit location clause out first: "in Downloads",
        # "from my Projects folder", "on the desktop", etc.
        location = ""
        location_match = re.search(
            r"\s+(?:in|inside|from|on)\s+(?:(?:my|the|a)\s+)?(.+?)\s*$",
            body,
            re.IGNORECASE,
        )
        if location_match:
            possible_location = location_match.group(1).strip()
            if possible_location:
                location = re.sub(
                    r"\b(?:folder|directory)\b\s*$", "", possible_location, flags=re.IGNORECASE
                ).strip()
                body = body[: location_match.start()].strip()

        # Support direct desktop/download/document wording as a location even
        # when no preposition was captured.
        if not location:
            trailing = re.search(
                r"\s+(?:on|from)\s+(?:my\s+|the\s+)?(desktop|downloads?|documents?)\s*$",
                original_body,
                re.IGNORECASE,
            )
            if trailing:
                location = trailing.group(1)
                body = original_body[: trailing.start()].strip()

        body = re.sub(r"^[\"']|[\"']$", "", body.strip()).strip()
        body = re.sub(
            r"^(?:(?:the|a)\s+)?(?:specific\s+)?(?:file|folder|document|directory)\s+"
            r"(?:(?:called|named)\s+|with\s+(?:the\s+)?name\s+)?",
            "",
            body,
            flags=re.IGNORECASE,
        ).strip()
        body = re.sub(r"^[\"']|[\"']$", "", body).strip()

        latest = body.casefold() in {
            "latest", "latest file", "most recent", "most recent file", "newest", "newest file",
        }
        explicit_file_language = bool(
            re.search(r"\b(?:file|folder|document|directory)\b", original_body, re.IGNORECASE)
        )
        looks_like_path = any(token in body for token in ("\\", "/", ":")) or "." in body
        lower_target = body.casefold()

        if lower_target in {
            "chrome", "google chrome", "teams", "microsoft teams", "calculator", "calc",
            "notepad", "explorer", "file explorer", "settings",
        }:
            return None

        if not (latest or location or explicit_file_language or looks_like_path):
            return None

        return body, location


    @staticmethod
    def _is_start_button_request(text: str) -> bool:
        return bool(
            re.search(r"\b(?:click|press|open|select)\s+(?:on\s+)?(?:the\s+)?(?:windows|start)\s*(?:button|menu)?\b", text)
        ) or text in {"windows button", "start button"}

    @staticmethod
    def _desktop_app_request(command: str) -> tuple[str | None, bool]:
        text = command.casefold().strip()
        match = re.search(r"(?:click|double-click|double click|open|launch|start|run)\s+(?:the\s+)?(.+?)(?:\s+(?:icon|app|application))?(?:\s+on my desktop|\s+on the desktop|\s+desktop icon|\s+from the taskbar)?$", text)
        if not match:
            return None, False
        raw_target = match.group(1).strip()
        as_admin = bool(re.search(r"\b(?:as|with)\s+administrator(?:\s+privileges)?\b|\badmin\b", raw_target))
        target = re.sub(r"\b(?:as|with)\s+administrator(?:\s+privileges)?\b|\badmin\b", "", raw_target).strip()
        target = re.sub(r"[^a-z0-9 ]+", " ", target).strip()
        aliases = {
            "chrome": "chrome", "google chrome": "chrome",
            "microsoft teams": "microsoft teams", "teams": "teams",
            "calculator": "calculator", "calc": "calc",
            "notepad": "notepad", "file explorer": "file explorer",
            "explorer": "explorer", "settings": "settings",
        }
        return aliases.get(target), as_admin

    @staticmethod
    def _semantic_click_target(command: str) -> str | None:
        text = command.strip()
        match = re.search(r"(?:click|press|select)\s+(?:the\s+)?(?:button|tab|link|menu item|item)?\s*[\"']?([^\"']+?)[\"']?$", text, re.IGNORECASE)
        if not match: return None
        target = match.group(1).strip()
        if not target or re.search(r"\d+\s*[, ]\s*\d+", target): return None
        return target

    @staticmethod
    def _coordinates(text: str) -> tuple[int, int] | None:
        match = re.search(r"(?:at|coordinates?\s*[:=]?)\s*(\d+)\s*[, ]\s*(\d+)", text)
        return (int(match.group(1)), int(match.group(2))) if match else None

    @staticmethod
    def _is_windows_intent(text: str) -> bool:
        actions = ("active", "focused", "minimize", "maximize", "restore", "click", "double click", "double-click", "right click", "right-click", "type ", "press ", "hotkey", "shortcut", "scroll", "select", "open ", "launch ", "start ", "run ", "show ")
        return ("window" in text or "desktop" in text or "screen" in text or any(term in text for term in actions)) and any(term in text for term in actions)

    @staticmethod
    def _describe_active_window(window: ActiveWindow) -> str:
        lines = [f"Active window: {window.title}"]
        if window.process_id is not None: lines.append(f"Process ID: {window.process_id}")
        if window.executable: lines.append(f"Executable: {window.executable}")
        return "\n".join(lines)
