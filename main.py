"""Application entry point for AI Gmail Organizer."""

import os
from pathlib import Path
import sys

from dotenv import load_dotenv
from PySide6.QtCore import Qt
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


def configure_desktop_window(window: OverlayWindow) -> None:
    """Turn the legacy overlay into a normal, user-friendly desktop window.

    The existing visual design is retained, but the application gets a real
    Windows top-level window. This prevents permission/confirmation dialogs
    from being trapped behind an always-on-top overlay and gives the user
    normal minimize/maximize/focus behavior.
    """
    # Remove the overlay-specific flags inherited from OverlayWindow.
    window.setWindowFlag(Qt.FramelessWindowHint, False)
    window.setWindowFlag(Qt.WindowStaysOnTopHint, False)
    window.setAttribute(Qt.WA_TranslucentBackground, False)

    # Use standard desktop window controls while keeping the existing UI.
    window.setWindowFlags(
        Qt.Window
        | Qt.WindowTitleHint
        | Qt.WindowSystemMenuHint
        | Qt.WindowMinimizeButtonHint
        | Qt.WindowMaximizeButtonHint
        | Qt.WindowCloseButtonHint
    )
    window.setMinimumSize(620, 420)
    window.resize(760, 540)
    window.setWindowTitle(window.windowTitle())

    # Make it a genuine top-level application window and ensure it is visible
    # when first launched. Child dialogs (OAuth, confirmations, permissions)
    # can now use this window as their parent without being hidden behind it.
    window.setAttribute(Qt.WA_DeleteOnClose, True)
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

    config_file = config_dir / ".env"
    credentials_file = config_dir / "credentials.json"
    if not config_file.exists() and not credentials_file.exists():
        setup = SetupDialog()
        setup.setWindowModality(Qt.ApplicationModal)
        setup.setWindowFlags(
            Qt.Dialog
            | Qt.WindowTitleHint
            | Qt.WindowSystemMenuHint
            | Qt.WindowCloseButtonHint
        )
        setup.show()
        setup.raise_()
        setup.activateWindow()
        setup.exec()
        load_dotenv(config_file, override=True)

    window = OverlayWindow()
    configure_desktop_window(window)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
