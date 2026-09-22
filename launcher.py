"""Packaged application launcher with first-run readiness checks."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from PySide6.QtWidgets import QApplication

from app.setup.runtime_dependencies import check_dependencies, missing_required
from app.ui.dependency_setup import DependencySetupDialog
from app.ui.overlay import OverlayWindow
from app.ui.setup_dialog import SetupDialog


def user_data_dir() -> Path:
    root = os.getenv("LOCALAPPDATA")
    path = Path(root) / "AI Gmail Organizer" if root else Path.home() / ".ai-gmail-organizer"
    path.mkdir(parents=True, exist_ok=True)
    return path


def configure_bundled_playwright() -> None:
    """Point Playwright at the browser runtime bundled inside a packaged build."""
    if not getattr(sys, "frozen", False):
        return
    bundled = Path(getattr(sys, "_MEIPASS", "")) / "playwright"
    if bundled.exists():
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(bundled))


def main() -> int:
    configure_bundled_playwright()
    config_dir = user_data_dir()
    load_dotenv(config_dir / ".env", override=True)
    app = QApplication(sys.argv)
    app.setApplicationName("AI Gmail Organizer")
    app.setOrganizationName("AI Gmail Organizer")

    config_file = config_dir / ".env"
    credentials_file = config_dir / "credentials.json"
    if not credentials_file.exists():
        SetupDialog().exec()
        load_dotenv(config_file, override=True)

    required_missing = missing_required()
    if required_missing:
        # Show the friendly setup UI instead of exposing Python/package names.
        DependencySetupDialog().exec()
        required_missing = missing_required()
        if required_missing:
            return 1

    optional_missing = [item for item in check_dependencies() if not item.available and not item.required]
    if optional_missing:
        DependencySetupDialog().exec()

    window = OverlayWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
