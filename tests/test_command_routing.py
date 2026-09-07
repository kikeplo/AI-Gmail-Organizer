from app.agent.commands import CommandAgent


def test_gmail_ui_task_routes_to_visual_control():
    assert CommandAgent._looks_like_gmail_ui_task("open starred on my gmail") is True
    assert CommandAgent._looks_like_gmail_ui_task("go to the promotions tab in Gmail") is True


def test_plain_windows_open_does_not_look_like_gmail_ui():
    assert CommandAgent._looks_like_gmail_ui_task("open calculator") is False


def test_split_task_understands_natural_chain():
    goal = "open Chrome, go to Gmail, and open Starred"
    assert CommandAgent._split_task(goal) == ["open Chrome", "go to Gmail", "open Starred"]


def test_split_task_preserves_non_action_and():
    goal = "open Chrome and search for AI engineering jobs"
    assert CommandAgent._split_task(goal) == ["open Chrome", "search for AI engineering jobs"]
