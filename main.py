"""Application entry point for AI Gmail Organizer."""

import os
from pathlib import Path
import sys

from dotenv import load_dotenv
from PySide6.QtWidgets import QApplication, QMessageBox

from app.ui.overlay import OverlayWindow
from app.ui.setup_dialog import SetupDialog


def user_data_dir() -> Path:
    """Return a per-user application-data directory."""
    root = os.getenv("LOCALAPPDATA")
    path = Path(root) / "AI Gmail Organizer" if root else Path.home() / ".ai-gmail-organizer"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_user_config() -> Path:
    """Load configuration from the current user's application-data directory."""
    config_dir = user_data_dir()
    load_dotenv(config_dir / ".env", override=True)
    return config_dir


def main() -> int:
    config_dir = load_user_config()
    app = QApplication(sys.argv)
    app.setApplicationName("AI Gmail Organizer")
    app.setOrganizationName("AI Gmail Organizer")

    config_file = config_dir / ".env"
    credentials_file = config_dir / "credentials.json"
    if not config_file.exists() and not credentials_file.exists():
        setup = SetupDialog()
        setup.exec()
        load_dotenv(config_file, override=True)

    window = OverlayWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
