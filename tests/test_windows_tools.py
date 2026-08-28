from app.windows.action_router import WindowsActionRouter
from app.windows.tools import ActiveWindow


class FakeWindowsTools:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_active_window(self) -> ActiveWindow:
        self.calls.append("active")
        return ActiveWindow(title="Visual Studio Code", process_id=1234, executable=r"C:\\Code.exe")

    def minimize_active_window(self) -> None:
        self.calls.append("minimize")

    def maximize_active_window(self) -> None:
        self.calls.append("maximize")

    def restore_active_window(self) -> None:
        self.calls.append("restore")


def test_active_window_intent() -> None:
    tools = FakeWindowsTools()
    response = WindowsActionRouter(tools).handle("What window is active?")
    assert response is not None
    assert "Visual Studio Code" in response.text
    assert tools.calls == ["active"]


def test_minimize_intent() -> None:
    tools = FakeWindowsTools()
    response = WindowsActionRouter(tools).handle("Minimize the active window")
    assert response is not None
    assert tools.calls == ["minimize"]


def test_non_windows_intent_is_ignored() -> None:
    tools = FakeWindowsTools()
    assert WindowsActionRouter(tools).handle("Organize my Gmail inbox") is None
    assert tools.calls == []
