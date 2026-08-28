"""Windows desktop automation tools for AI Gmail Organizer."""

from __future__ import annotations

from dataclasses import dataclass
import os
import subprocess
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class ActiveWindow:
    title: str
    process_id: int | None = None
    executable: str | None = None


class WindowsTools:
    """Windows automation surface for windows, apps, mouse, and keyboard."""

    APP_ALIASES = {
        "chrome": ("chrome", "chrome.exe", "GoogleChromeAutoLaunch_"),
        "google chrome": ("chrome", "chrome.exe", "GoogleChromeAutoLaunch_"),
        "microsoft teams": ("ms-teams:",),
        "teams": ("ms-teams:",),
        "calculator": ("calc.exe",),
        "notepad": ("notepad.exe",),
        "file explorer": ("explorer.exe",),
        "explorer": ("explorer.exe",),
        "settings": ("ms-settings:",),
    }

    def get_active_window(self) -> ActiveWindow:
        if os.name != "nt": raise OSError("Windows automation is only available on Windows.")
        import win32api, win32gui, win32process
        hwnd = win32gui.GetForegroundWindow(); title = win32gui.GetWindowText(hwnd).strip() or "(untitled window)"
        _, process_id = win32process.GetWindowThreadProcessId(hwnd); executable = None
        try:
            handle = win32api.OpenProcess(0x1000 | 0x0010, False, process_id)
            try: executable = win32process.GetModuleFileNameEx(handle, 0)
            finally: win32api.CloseHandle(handle)
        except Exception: pass
        return ActiveWindow(title, process_id, executable)

    def minimize_active_window(self): self._set_window_state("minimize")
    def maximize_active_window(self): self._set_window_state("maximize")
    def restore_active_window(self): self._set_window_state("restore")

    def move_mouse(self, x: int, y: int, duration: float = 0.2):
        if os.name != "nt": raise OSError("Windows automation is only available on Windows.")
        import pyautogui
        w, h = pyautogui.size()
        if not (0 <= x < w and 0 <= y < h): raise ValueError(f"Mouse position ({x}, {y}) is outside the screen.")
        pyautogui.moveTo(x, y, duration=max(0.0, duration)); return x, y

    def click(self, x: int | None = None, y: int | None = None, button: str = "left", clicks: int = 1):
        if os.name != "nt": raise OSError("Windows automation is only available on Windows.")
        import pyautogui
        if x is not None and y is not None: self.move_mouse(x, y)
        if button not in {"left", "right", "middle"}: raise ValueError("Mouse button must be left, right, or middle.")
        if clicks < 1 or clicks > 3: raise ValueError("Clicks must be between 1 and 3.")
        position = pyautogui.position(); pyautogui.click(button=button, clicks=clicks, interval=0.12)
        return int(position.x), int(position.y)

    def double_click(self, x=None, y=None): return self.click(x, y, clicks=2)

    def scroll(self, clicks: int):
        if os.name != "nt": raise OSError("Windows automation is only available on Windows.")
        import pyautogui
        if clicks: pyautogui.scroll(clicks)

    def press(self, key: str):
        if os.name != "nt": raise OSError("Windows automation is only available on Windows.")
        import pyautogui
        normalized = key.casefold().strip(); allowed = {"enter","esc","tab","space","backspace","delete","home","end","pageup","pagedown","up","down","left","right"}
        if normalized not in allowed and not (len(normalized) == 1 and normalized.isprintable()): raise ValueError("Unsupported key.")
        pyautogui.press(normalized)

    def hotkey(self, *keys: str):
        if os.name != "nt": raise OSError("Windows automation is only available on Windows.")
        import pyautogui
        if not keys or len(keys) > 4: raise ValueError("A hotkey must contain between 1 and 4 keys.")
        pyautogui.hotkey(*[key.casefold().strip() for key in keys])

    def type_text(self, text: str, interval: float = 0.01):
        if os.name != "nt": raise OSError("Windows automation is only available on Windows.")
        if len(text) > 4000: raise ValueError("Text entry is limited to 4000 characters per action.")
        import pyautogui; pyautogui.write(text, interval=max(0.0, interval))

    def screenshot(self, path=None):
        if os.name != "nt": raise OSError("Windows automation is only available on Windows.")
        import pyautogui
        image = pyautogui.screenshot()
        if path: image.save(path)
        return image

    def launch_application(self, executable: str, args: Sequence[str] = ()):
        if os.name != "nt": raise OSError("Windows automation is only available on Windows.")
        target = executable.strip()
        if not target: raise ValueError("Application name cannot be empty.")
        # Windows shell launch supports installed app protocols and registered apps.
        if target.endswith(":") or target.startswith("ms-"):
            os.startfile(target)
            return
        subprocess.Popen([target, *args], shell=False)

    def launch_named_application(self, name: str) -> str:
        if os.name != "nt": raise OSError("Windows automation is only available on Windows.")
        query = name.casefold().strip()
        candidates = self.APP_ALIASES.get(query)
        if candidates is None:
            for alias, values in self.APP_ALIASES.items():
                if query == alias or alias in query or query in alias:
                    candidates = values; break
        if candidates is None: raise FileNotFoundError(f"I don't have a safe launcher mapping for '{name}'.")
        last_error = None
        for target in candidates:
            try:
                if target.endswith(":") or target.startswith("ms-"):
                    os.startfile(target)
                elif target in {"chrome", "chrome.exe"}:
                    try: subprocess.Popen([target], shell=False)
                    except FileNotFoundError: os.startfile("chrome")
                else:
                    subprocess.Popen([target], shell=False)
                return f"Opened {name}."
            except Exception as exc: last_error = exc
        raise FileNotFoundError(f"Could not open {name}. {last_error}")

    @staticmethod
    def _set_window_state(state: str):
        if os.name != "nt": raise OSError("Windows automation is only available on Windows.")
        import win32con, win32gui
        hwnd = win32gui.GetForegroundWindow(); commands = {"minimize": win32con.SW_MINIMIZE, "maximize": win32con.SW_MAXIMIZE, "restore": win32con.SW_RESTORE}
        if state not in commands: raise ValueError(f"Unsupported window state: {state}")
        win32gui.ShowWindow(hwnd, commands[state])
