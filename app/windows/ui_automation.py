"""Windows UI Automation helpers for semantic element discovery and activation."""

from __future__ import annotations

from dataclasses import dataclass


class UIAutomationError(RuntimeError):
    pass


@dataclass(frozen=True)
class UIElement:
    name: str
    control_type: str
    automation_id: str = ""
    x: int = 0
    y: int = 0


class WindowsUIAutomation:
    """Best-effort semantic Windows UI Automation using pywinauto when installed."""

    def __init__(self) -> None:
        self._pywinauto = None

    def _load(self):
        if self._pywinauto is None:
            try:
                from pywinauto import Desktop
                self._pywinauto = Desktop
            except ImportError as exc:
                raise UIAutomationError("Windows UI Automation is not installed. Install pywinauto to enable semantic controls.") from exc
        return self._pywinauto

    def list_visible(self, max_items: int = 80) -> list[UIElement]:
        Desktop = self._load()
        try:
            window = Desktop(backend="uia").get_active()
            items: list[UIElement] = []
            for control in window.descendants()[:max(1, max_items)]:
                try:
                    name = (control.window_text() or "").strip()
                    control_type = str(control.element_info.control_type or "")
                    automation_id = str(control.element_info.automation_id or "")
                    if not name and not automation_id:
                        continue
                    rect = control.rectangle()
                    items.append(UIElement(name, control_type, automation_id, int((rect.left + rect.right) / 2), int((rect.top + rect.bottom) / 2)))
                except Exception:
                    continue
            return items
        except Exception as exc:
            raise UIAutomationError(f"Could not inspect the active Windows UI: {exc}") from exc

    def find(self, text: str, max_items: int = 80) -> list[UIElement]:
        query = text.casefold().strip()
        if not query:
            return []
        return [item for item in self.list_visible(max_items) if query in item.name.casefold()]

    def click(self, text: str) -> UIElement:
        Desktop = self._load()
        query = text.casefold().strip()
        if not query:
            raise UIAutomationError("The UI element name cannot be empty.")
        try:
            window = Desktop(backend="uia").get_active()
            candidates = [c for c in window.descendants() if query in (c.window_text() or "").casefold()]
            if not candidates:
                raise UIAutomationError(f"Could not find a visible UI element named '{text}'.")
            control = candidates[0]
            try:
                control.invoke()
            except Exception:
                control.click_input()
            rect = control.rectangle()
            return UIElement(control.window_text() or text, str(control.element_info.control_type or ""), str(control.element_info.automation_id or ""), int((rect.left + rect.right) / 2), int((rect.top + rect.bottom) / 2))
        except UIAutomationError:
            raise
        except Exception as exc:
            raise UIAutomationError(f"Could not activate '{text}': {exc}") from exc
