"""Application entry point for AI Gmail Organizer."""

import os
from pathlib import Path
import sys

from dotenv import load_dotenv
from PySide6.QtWidgets import QApplication

from app.ui.overlay import OverlayWindow


def user_data_dir() -> Path:
    """Return a per-user application-data directory."""
    root = os.getenv("LOCALAPPDATA")
    if root:
        path = Path(root) / "AI Gmail Organizer"
    else:
        path = Path.home() / ".ai-gmail-organizer"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_user_config() -> Path:
    """Load user-local configuration without requiring secrets in the repository."""
    config_dir = user_data_dir()
    load_dotenv(config_dir / ".env", override=False)
    return config_dir


def main() -> int:
    load_user_config()
    app = QApplication(sys.argv)
    app.setApplicationName("AI Gmail Organizer")
    app.setOrganizationName("AI Gmail Organizer")

    window = OverlayWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
