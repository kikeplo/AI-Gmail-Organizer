"""Application entry point for AI Gmail Organizer."""

import os
from pathlib import Path
import sys

from dotenv import load_dotenv
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.agent.access import AccessManager
from app.ui.desktop_access import DesktopAccessDialog
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


def resource_path(relative: str) -> Path:
    """Resolve a bundled resource in both source and PyInstaller builds."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative


def configure_desktop_window(window: OverlayWindow) -> None:
    """Keep the original rounded UI while behaving as a normal desktop window."""
    window.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
    window.setWindowFlag(Qt.WindowStaysOnTopHint, False)
    window.setAttribute(Qt.WA_TranslucentBackground, True)
    window.setMinimumSize(780, 540)
    window.resize(960, 680)
    window.setAttribute(Qt.WA_DeleteOnClose, True)

    icon_path = resource_path("assets/ai_gmail_organizer.svg")
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))

    window.show()
    window.raise_()
    window.activateWindow()
    window.setFocus()


def main() -> int:
    config_dir = load_user_config()
    app = QApplication(sys.argv)
    app.setApplicationName("AI Gmail Organizer")
    app.setOrganizationName("AI Gmail Organizer")
    app.setQuitOnLastWindowClosed(True)

    icon_path = resource_path("assets/ai_gmail_organizer.svg")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    config_file = config_dir / ".env"
    credentials_file = config_dir / "credentials.json"
    if not config_file.exists() and not credentials_file.exists():
        setup = SetupDialog()
        setup.setWindowModality(Qt.ApplicationModal)
        setup.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint)
        setup.show()
        setup.raise_()
        setup.activateWindow()
        setup.exec()
        load_dotenv(config_file, override=True)

    # Permission consent is completed synchronously on Qt's main thread.
    # The worker thread is not created until after the user has responded.
    access = AccessManager()
    if not access.is_allowed("screen") or not access.is_allowed("input") or not access.is_allowed("browser"):
        dialog = DesktopAccessDialog(access, parent=None)
        dialog.setWindowModality(Qt.ApplicationModal)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        if dialog.exec() != dialog.Accepted:
            # The app remains usable for Gmail/local AI; desktop capabilities stay disabled.
            pass

    window = OverlayWindow()
    configure_desktop_window(window)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
