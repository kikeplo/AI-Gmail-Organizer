"""Windows desktop automation tools for AI Gmail Organizer."""

from __future__ import annotations

from dataclasses import dataclass
import os
import subprocess
import time
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class ActiveWindow:
    title: str
    process_id: int | None = None
    executable: str | None = None
    hwnd: int | None = None


class WindowsTools:
    """Windows automation surface for apps, files, folders, windows, mouse, keyboard, and foreground tracking."""

    APP_ALIASES = {
        "chrome": ("chrome", "chrome.exe"),
        "google chrome": ("chrome", "chrome.exe"),
        "microsoft teams": ("msteams:", "ms-teams:", "ms-teams.exe"),
        "teams": ("msteams:", "ms-teams:", "ms-teams.exe"),
        "calculator": ("calc.exe",),
        "notepad": ("notepad.exe",),
        "file explorer": ("explorer.exe",),
        "explorer": ("explorer.exe",),
        "settings": ("ms-settings:",),
    }

    def __init__(self) -> None:
        self._own_hwnd: int | None = None
        self._last_external: ActiveWindow | None = None

    def set_own_window(self, hwnd: int | None) -> None:
        self._own_hwnd = hwnd

    def update_last_external_window(self) -> ActiveWindow | None:
        current = self._read_foreground_window()
        if current is None:
            return self._last_external
        if self._own_hwnd is not None and current.hwnd == self._own_hwnd:
            return self._last_external
        if current.executable and self._is_organizer_process(current.executable):
            return self._last_external
        self._last_external = current
        return current

    def get_active_window(self, external: bool = False) -> ActiveWindow:
        if os.name != "nt":
            raise OSError("Windows automation is only available on Windows.")
        if external:
            return self.get_last_external_window()
        current = self._read_foreground_window()
        if current is None:
            raise OSError("Could not determine the foreground window.")
        return current

    def get_last_external_window(self) -> ActiveWindow:
        last = self.update_last_external_window()
        if last is None:
            raise OSError("No external application window has been observed yet. Open or focus another app first.")
        return last

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

    def open_file_or_folder(self, target: str, location_hint: str = "") -> str:
        """Open a requested file/folder by exact path or by filename in common user folders."""
        if os.name != "nt": raise OSError("Opening Windows files is only available on Windows.")
        raw = target.strip().strip('"\'')
        if not raw:
            raise ValueError("Please specify the file or folder to open.")

        candidate = Path(os.path.expandvars(os.path.expanduser(raw)))
        if candidate.exists():
            os.startfile(str(candidate))
            return f"Opened {candidate.name or candidate}."

        home = Path.home()
        desktop = Path(os.getenv("USERPROFILE", str(home))) / "Desktop"
        downloads = home / "Downloads"
        documents = home / "Documents"
        hint = location_hint.casefold()
        roots: list[Path] = []
        if "desktop" in hint: roots.append(desktop)
        elif "download" in hint: roots.append(downloads)
        elif "document" in hint: roots.append(documents)
        roots.extend(path for path in (desktop, downloads, documents) if path not in roots)

        target_name = Path(raw).name.casefold()
        target_stem = Path(raw).stem.casefold()
        matches: list[Path] = []
        for root in roots:
            if not root.is_dir():
                continue
            try:
                for path in root.rglob("*"):
                    if len(matches) >= 20: break
                    if not path.is_file() and not path.is_dir(): continue
                    name = path.name.casefold()
                    if name == target_name or ("." not in raw and path.stem.casefold() == target_stem):
                        matches.append(path)
                if matches and ("desktop" in hint or "download" in hint or "document" in hint): break
            except (OSError, PermissionError):
                continue

        unique: list[Path] = []
        seen: set[str] = set()
        for path in matches:
            key = str(path).casefold()
            if key not in seen:
                seen.add(key); unique.append(path)
        if not unique:
            raise FileNotFoundError(f"I couldn't find '{raw}' in Desktop, Downloads, or Documents.")
        if len(unique) > 1:
            choices = "\n".join(f"• {path}" for path in unique[:5])
            raise FileExistsError(f"I found multiple matches for '{raw}'. Please specify the location.\n\n{choices}")
        path = unique[0]
        os.startfile(str(path))
        return f"Opened {path.name}."

    def launch_application(self, executable: str, args: Sequence[str] = ()):
        if os.name != "nt": raise OSError("Windows automation is only available on Windows.")
        target = executable.strip()
        if not target: raise ValueError("Application name cannot be empty.")
        if target.endswith(":") or target.startswith("ms-"):
            os.startfile(target); return
        subprocess.Popen([target, *args], shell=False)

    def launch_application_as_admin(self, executable: str, args: Sequence[str] = ()):
        """Explicitly request Windows UAC elevation for an application."""
        if os.name != "nt": raise OSError("Windows elevation is only available on Windows.")
        import ctypes
        target = executable.strip()
        if not target: raise ValueError("Application name cannot be empty.")
        params = " ".join(self._quote_windows_arg(arg) for arg in args)
        result = ctypes.windll.shell32.ShellExecuteW(None, "runas", target, params or None, None, 1)
        if result <= 32:
            raise OSError(f"Windows could not start the application with administrator privileges (code {result}).")

    def launch_named_application(self, name: str, as_admin: bool = False) -> str:
        if os.name != "nt": raise OSError("Windows automation is only available on Windows.")
        query = name.casefold().strip()
        candidates = self.APP_ALIASES.get(query)
        if candidates is None:
            for alias, values in self.APP_ALIASES.items():
                if query == alias or alias in query or query in alias:
                    candidates = values; break
        if candidates is None:
            raise FileNotFoundError(f"I don't have a safe launcher mapping for '{name}'.")
        last_error = None
        for target in candidates:
            try:
                if target.endswith(":") or target.startswith("ms-"):
                    if as_admin: raise OSError("This app uses a Windows protocol and cannot be elevated by this launcher.")
                    os.startfile(target)
                elif as_admin:
                    self.launch_application_as_admin(target)
                else:
                    try: subprocess.Popen([target], shell=False)
                    except FileNotFoundError: os.startfile(target)
                time.sleep(0.25); self.update_last_external_window()
                return f"Opened {name}{' with administrator privileges' if as_admin else ''}."
            except Exception as exc: last_error = exc
        raise FileNotFoundError(f"Could not open {name}. {last_error}")

    @staticmethod
    def _quote_windows_arg(value: str) -> str:
        if not value or any(ch.isspace() for ch in value) or '"' in value:
            return '"' + value.replace('"', '\\"') + '"'
        return value

    @staticmethod
    def _is_organizer_process(executable: str) -> bool:
        return "AI-Gmail-Organizer".casefold() in Path(executable).name.casefold()

    @staticmethod
    def _read_foreground_window() -> ActiveWindow | None:
        if os.name != "nt": return None
        import win32api, win32gui, win32process
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd: return None
        title = win32gui.GetWindowText(hwnd).strip() or "(untitled window)"
        _, process_id = win32process.GetWindowThreadProcessId(hwnd)
        executable = None
        try:
            handle = win32api.OpenProcess(0x1000 | 0x0010, False, process_id)
            try: executable = win32process.GetModuleFileNameEx(handle, 0)
            finally: win32api.CloseHandle(handle)
        except Exception: pass
        return ActiveWindow(title, process_id, executable, int(hwnd))

    @staticmethod
    def _set_window_state(state: str):
        if os.name != "nt": raise OSError("Windows automation is only available on Windows.")
        import win32con, win32gui
        hwnd = win32gui.GetForegroundWindow(); commands = {"minimize": win32con.SW_MINIMIZE, "maximize": win32con.SW_MAXIMIZE, "restore": win32con.SW_RESTORE}
        if state not in commands: raise ValueError(f"Unsupported window state: {state}")
        win32gui.ShowWindow(hwnd, commands[state])
