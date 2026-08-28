"""Windows desktop automation tools for AI Gmail Organizer v1.3."""

from __future__ import annotations

from dataclasses import dataclass
import os
import subprocess
from typing import Sequence


@dataclass(frozen=True)
class ActiveWindow:
    """Metadata for the currently focused Windows application window."""

    title: str
    process_id: int | None = None
    executable: str | None = None


class WindowsTools:
    """Windows automation surface for window, mouse, keyboard, and app control."""

    def get_active_window(self) -> ActiveWindow:
        if os.name != "nt":
            raise OSError("Windows automation is only available on Windows.")
        import win32api
        import win32gui
        import win32process
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd).strip() or "(untitled window)"
        _, process_id = win32process.GetWindowThreadProcessId(hwnd)
        executable: str | None = None
        try:
            handle = win32api.OpenProcess(0x1000 | 0x0010, False, process_id)
            try:
                executable = win32process.GetModuleFileNameEx(handle, 0)
            finally:
                win32api.CloseHandle(handle)
        except Exception:
            executable = None
        return ActiveWindow(title=title, process_id=process_id, executable=executable)

    def minimize_active_window(self) -> None:
        self._set_window_state("minimize")

    def maximize_active_window(self) -> None:
        self._set_window_state("maximize")

    def restore_active_window(self) -> None:
        self._set_window_state("restore")

    def move_mouse(self, x: int, y: int, duration: float = 0.2) -> tuple[int, int]:
        if os.name != "nt":
            raise OSError("Windows automation is only available on Windows.")
        import pyautogui
        screen_w, screen_h = pyautogui.size()
        if not (0 <= x < screen_w and 0 <= y < screen_h):
            raise ValueError(f"Mouse position ({x}, {y}) is outside the screen.")
        pyautogui.moveTo(x, y, duration=max(0.0, duration))
        return x, y

    def click(self, x: int | None = None, y: int | None = None, button: str = "left", clicks: int = 1) -> tuple[int, int]:
        if os.name != "nt":
            raise OSError("Windows automation is only available on Windows.")
        import pyautogui
        if x is not None and y is not None:
            self.move_mouse(x, y)
        position = pyautogui.position()
        if button not in {"left", "right", "middle"}:
            raise ValueError("Mouse button must be left, right, or middle.")
        if clicks < 1 or clicks > 3:
            raise ValueError("Clicks must be between 1 and 3.")
        pyautogui.click(button=button, clicks=clicks, interval=0.12)
        return int(position.x), int(position.y)

    def double_click(self, x: int | None = None, y: int | None = None) -> tuple[int, int]:
        return self.click(x, y, clicks=2)

    def scroll(self, clicks: int) -> None:
        if os.name != "nt":
            raise OSError("Windows automation is only available on Windows.")
        import pyautogui
        if clicks == 0:
            return
        pyautogui.scroll(clicks)

    def press(self, key: str) -> None:
        if os.name != "nt":
            raise OSError("Windows automation is only available on Windows.")
        import pyautogui
        allowed = {"enter", "esc", "tab", "space", "backspace", "delete", "home", "end", "pageup", "pagedown", "up", "down", "left", "right"}
        normalized = key.casefold().strip()
        if normalized not in allowed and not (len(normalized) == 1 and normalized.isprintable()):
            raise ValueError("Unsupported key.")
        pyautogui.press(normalized)

    def hotkey(self, *keys: str) -> None:
        if os.name != "nt":
            raise OSError("Windows automation is only available on Windows.")
        import pyautogui
        if not keys or len(keys) > 4:
            raise ValueError("A hotkey must contain between 1 and 4 keys.")
        pyautogui.hotkey(*[key.casefold().strip() for key in keys])

    def type_text(self, text: str, interval: float = 0.01) -> None:
        if os.name != "nt":
            raise OSError("Windows automation is only available on Windows.")
        if len(text) > 4000:
            raise ValueError("Text entry is limited to 4000 characters per action.")
        import pyautogui
        pyautogui.write(text, interval=max(0.0, interval))

    def screenshot(self, path: str | None = None):
        if os.name != "nt":
            raise OSError("Windows automation is only available on Windows.")
        import pyautogui
        image = pyautogui.screenshot()
        if path:
            image.save(path)
        return image

    def launch_application(self, executable: str, args: Sequence[str] = ()) -> None:
        if os.name != "nt":
            raise OSError("Windows automation is only available on Windows.")
        if not executable.strip():
            raise ValueError("Executable path cannot be empty.")
        subprocess.Popen([executable, *args], shell=False)

    @staticmethod
    def _set_window_state(state: str) -> None:
        if os.name != "nt":
            raise OSError("Windows automation is only available on Windows.")
        import win32gui
        import win32con
        hwnd = win32gui.GetForegroundWindow()
        commands = {"minimize": win32con.SW_MINIMIZE, "maximize": win32con.SW_MAXIMIZE, "restore": win32con.SW_RESTORE}
        if state not in commands:
            raise ValueError(f"Unsupported window state: {state}")
        win32gui.ShowWindow(hwnd, commands[state])
