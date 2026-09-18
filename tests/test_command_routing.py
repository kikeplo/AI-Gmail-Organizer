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


def test_start_button_command_uses_windows_router(monkeypatch) -> None:
    from app.agent.commands import CommandAgent

    agent = CommandAgent()
    calls = []

    def fake_handle(command):
        calls.append(command)
        from app.windows.action_router import WindowActionResponse
        return WindowActionResponse("Opened the Windows Start menu.", mode="windows_start")

    monkeypatch.setattr(agent.windows, "handle", fake_handle)
    response = agent.respond("Click on Windows")

    assert response.mode == "windows_start"
    assert response.text == "Opened the Windows Start menu."
    assert calls == ["Click on Windows"]


def test_complex_prompt_is_detected_for_cloud_routing():
    from app.ai.router import SmartAIRouter

    assert SmartAIRouter._is_complex_prompt(
        "Please compare these architectures in depth, explain the trade-offs, and propose a step-by-step implementation strategy."
    ) is True


def test_simple_prompt_is_not_marked_complex():
    from app.ai.router import SmartAIRouter

    assert SmartAIRouter._is_complex_prompt("What is a neural network?") is False


def test_general_conversation_uses_router_instead_of_direct_local_fast_path():
    assert CommandAgent._should_use_local_ai("What is the difference between TCP and UDP?") is False
