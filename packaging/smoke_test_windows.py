"""Post-build smoke tests for the portable Windows package."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "dist" / "AI-Gmail-Organizer"
EXE = APP_DIR / "AI-Gmail-Organizer.exe"


def check_imports() -> None:
    import PIL  # noqa: F401
    import pyautogui  # noqa: F401
    import pyscreeze  # noqa: F401
    import pywinauto  # noqa: F401
    import playwright  # noqa: F401


def check_packaged_app_modules() -> None:
    matches = list(APP_DIR.rglob("action_router.py")) + list(APP_DIR.rglob("action_router.pyc"))
    if not matches:
        raise RuntimeError(
            "The portable package is missing app/windows/action_router.py or action_router.pyc. "
            "The application's Windows action router was not collected."
        )
    required = {
        "tools": list(APP_DIR.rglob("tools.py")) + list(APP_DIR.rglob("tools.pyc")),
        "ui_automation": list(APP_DIR.rglob("ui_automation.py")) + list(APP_DIR.rglob("ui_automation.pyc")),
    }
    missing = [name for name, files in required.items() if not files]
    if missing:
        raise RuntimeError(
            "The portable package is missing application Windows modules: "
            + ", ".join(missing)
        )
    print("Packaged application modules found:")
    for path in matches[:1]:
        print(f"  action_router: {path}")


def find_chrome() -> Path:
    matches = list((APP_DIR / "playwright").rglob("chrome.exe"))
    if not matches:
        raise RuntimeError("Bundled Chromium chrome.exe was not found.")
    return matches[0]


def check_playwright(chrome: Path) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=str(chrome), headless=True)
        page = browser.new_page()
        page.set_content("<title>AI Gmail Organizer smoke test</title>")
        if page.title() != "AI Gmail Organizer smoke test":
            raise RuntimeError("Playwright could not use the bundled Chromium runtime.")
        browser.close()


def check_exe_starts() -> None:
    env = os.environ.copy()
    process = subprocess.Popen([str(EXE)], cwd=str(APP_DIR), env=env)
    try:
        time.sleep(4)
        if process.poll() is not None:
            raise RuntimeError(f"Packaged EXE exited immediately with code {process.returncode}.")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


def main() -> int:
    if not APP_DIR.is_dir():
        raise RuntimeError(f"Missing application folder: {APP_DIR}")
    if not EXE.is_file():
        raise RuntimeError(f"Missing application EXE: {EXE}")
    check_imports()
    check_packaged_app_modules()
    chrome = find_chrome()
    check_playwright(chrome)
    check_exe_starts()
    print(f"Smoke test passed: {EXE}")
    print(f"Chromium passed: {chrome}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
