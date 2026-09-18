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


def test_file_request_accepts_named_file_without_extension() -> None:
    parsed = WindowsActionRouter._file_request("Open the specific file called report")
    assert parsed == ("report", "")


def test_file_request_accepts_latest_with_named_folder() -> None:
    parsed = WindowsActionRouter._file_request("Open the latest in my Projects folder")
    assert parsed == ("latest", "Projects")


def test_start_button_request() -> None:
    assert WindowsActionRouter._is_start_button_request("Click on Windows")
    assert WindowsActionRouter._is_start_button_request("Open the Start button")


def test_file_request_accepts_specific_named_file() -> None:
    parsed = WindowsActionRouter._file_request(
        "Open the specific file with the name budget.xlsx"
    )
    assert parsed == ("budget.xlsx", "")


def test_file_request_accepts_polite_phrasing() -> None:
    parsed = WindowsActionRouter._file_request("Can you open the latest file in my downloads folder")
    assert parsed == ("latest file", "downloads")


def test_file_request_preserves_typo_for_resolver() -> None:
    parsed = WindowsActionRouter._file_request("Open the latest file in my downlaod folder")
    assert parsed == ("latest file", "downlaod")
