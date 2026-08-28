"""Windows desktop automation tools for AI Gmail Organizer v0.6."""

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
    """Small, Windows-only automation surface with explicit operations."""

    def get_active_window(self) -> ActiveWindow:
        """Return title and process metadata for the foreground window."""
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
            # Some protected/system processes cannot expose their executable path.
            executable = None

        return ActiveWindow(title=title, process_id=process_id, executable=executable)

    def minimize_active_window(self) -> None:
        """Minimize the currently focused window."""
        self._set_window_state("minimize")

    def maximize_active_window(self) -> None:
        """Maximize the currently focused window."""
        self._set_window_state("maximize")

    def restore_active_window(self) -> None:
        """Restore the currently focused window to its previous size."""
        self._set_window_state("restore")

    def launch_application(self, executable: str, args: Sequence[str] = ()) -> None:
        """Launch an executable using Windows process creation.

        The caller should provide a trusted executable path rather than passing
        arbitrary shell text. ``shell=False`` prevents command-string injection.
        """
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
        commands = {
            "minimize": win32con.SW_MINIMIZE,
            "maximize": win32con.SW_MAXIMIZE,
            "restore": win32con.SW_RESTORE,
        }
        if state not in commands:
            raise ValueError(f"Unsupported window state: {state}")
        win32gui.ShowWindow(hwnd, commands[state])
