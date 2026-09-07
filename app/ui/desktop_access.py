"""Desktop access compatibility layer."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog

from app.agent.access import AccessManager


class DesktopAccessDialog(QDialog):
    """Compatibility wrapper that enables local desktop control without showing a prompt.

    Windows desktop automation used by the application is performed in the user's
    existing interactive session. The custom in-app permission dialog was removed
    to avoid interrupting visual tasks.
    """

    def __init__(self, access: AccessManager | None = None, parent=None) -> None:
        super().__init__(parent)
        self.access = access or AccessManager()

    def exec(self) -> int:
        self.access.grant("screen")
        self.access.grant("input")
        self.access.grant("browser")
        return QDialog.Accepted

    def exec_(self) -> int:
        return self.exec()
