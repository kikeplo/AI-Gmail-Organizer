"""First-run dependency diagnostics and setup helpers for Windows builds."""

from __future__ import annotations

import importlib
import importlib.util
import os
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class DependencyStatus:
    name: str
    available: bool
    required: bool
    detail: str


def _module_available(module: str) -> bool:
    """Check a dependency in both normal and PyInstaller-frozen environments."""
    try:
        if importlib.util.find_spec(module) is not None:
            return True
    except (ImportError, ModuleNotFoundError, ValueError, AttributeError):
        pass
    try:
        importlib.import_module(module)
        return True
    except Exception:
        return False


def _windows_input_ready() -> bool:
    if os.name != "nt":
        return False
    # PyAutoGUI is the actual runtime dependency used by WindowsTools.
    if not _module_available("pyautogui"):
        return False
    try:
        import pyautogui
        # Do not take a screenshot or move the pointer during startup; just verify
        # the module exposes the runtime surface the app uses.
        return all(hasattr(pyautogui, name) for name in ("size", "position", "click", "press", "write", "scroll", "screenshot"))
    except Exception:
        return False


def check_dependencies() -> list[DependencyStatus]:
    return [
        DependencyStatus("PySide6", _module_available("PySide6"), True, "Desktop interface"),
        DependencyStatus("Google Gmail", _module_available("googleapiclient"), True, "Gmail integration"),
        DependencyStatus("Windows input", _windows_input_ready(), True, "Mouse and keyboard control"),
        DependencyStatus("Windows UI Automation", os.name == "nt" and _module_available("pywinauto"), False, "Semantic desktop controls"),
        DependencyStatus("Browser automation", _module_available("playwright"), False, "Chrome and website automation"),
    ]


def browser_runtime_ready() -> bool:
    if not _module_available("playwright"):
        return False
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            executable = playwright.chromium.executable_path
        return bool(executable and os.path.exists(executable))
    except Exception:
        return False


def missing_required(statuses: list[DependencyStatus] | None = None) -> list[DependencyStatus]:
    statuses = statuses or check_dependencies()
    return [item for item in statuses if item.required and not item.available]


def repair_optional_dependencies() -> list[str]:
    """Repair optional components for source installs; packaged builds are expected to bundle them."""
    if getattr(sys, "frozen", False):
        return ["This EXE is designed to include optional components during packaging. Rebuild with the latest installer script if anything is missing."]
    actions: list[str] = []
    commands: list[list[str]] = []
    if os.name == "nt" and not _module_available("pywinauto"):
        commands.append([sys.executable, "-m", "pip", "install", "pywinauto>=0.6.8,<1"])
    if not _module_available("playwright"):
        commands.append([sys.executable, "-m", "pip", "install", "playwright>=1.50,<2"])
    for command in commands:
        subprocess.run(command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        actions.append(" ".join(command[3:]))
    if _module_available("playwright") and not browser_runtime_ready():
        env = os.environ.copy()
        env.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        actions.append("Playwright Chromium runtime")
    return actions
