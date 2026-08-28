"""First-run dependency diagnostics and optional self-repair for packaged Windows builds."""

from __future__ import annotations

import importlib.util
import os
import shutil
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
    return importlib.util.find_spec(module) is not None


def check_dependencies() -> list[DependencyStatus]:
    statuses = [
        DependencyStatus("PySide6", _module_available("PySide6"), True, "Desktop interface"),
        DependencyStatus("Google Gmail", _module_available("googleapiclient"), True, "Gmail integration"),
        DependencyStatus("Windows automation", os.name == "nt" and _module_available("pyautogui"), True, "Mouse and keyboard control"),
        DependencyStatus("Windows UI Automation", os.name == "nt" and _module_available("pywinauto"), False, "Semantic desktop controls"),
        DependencyStatus("Browser automation", _module_available("playwright"), False, "Chrome and website automation"),
    ]
    return statuses


def missing_required(statuses: list[DependencyStatus] | None = None) -> list[DependencyStatus]:
    statuses = statuses or check_dependencies()
    return [item for item in statuses if item.required and not item.available]


def browser_runtime_ready() -> bool:
    if not _module_available("playwright"):
        return False
    chrome = shutil.which("chrome") or shutil.which("chromium")
    if chrome:
        return True
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            executable = playwright.chromium.executable_path
        return bool(executable and os.path.exists(executable))
    except Exception:
        return False


def repair_optional_dependencies() -> list[str]:
    """Install missing optional Python/browser components using the active Python runtime."""
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
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        actions.append("Playwright Chromium runtime")
    return actions
