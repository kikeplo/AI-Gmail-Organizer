"""Application entry point for AI Gmail Organizer."""

import sys

from PySide6.QtWidgets import QApplication

from app.ui.overlay import OverlayWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("AI Gmail Organizer")
    app.setOrganizationName("AI Gmail Organizer")

    window = OverlayWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
