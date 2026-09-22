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



def test_local_only_calls_local_engine_without_availability_preflight(monkeypatch) -> None:
    from app.ai.provider import AIProvider
    from app.ai.local_engine import LocalAIError
    from app.ai.router import SmartAIRouter

    class FakeCloud:
        configured = True
        provider = "Fake Cloud"

        def chat(self, prompt, system):
            raise AssertionError("Cloud AI must not be called in Local-only mode.")

        def _protocol(self):
            return "Fake Cloud"

    class FakeLocal:
        enabled = True

        def available(self):
            return False

        def chat(self, prompt, system):
            return "Local answer"

    monkeypatch.setenv("AI_ROUTING_MODE", "local-only")
    router = SmartAIRouter(cloud_factory=FakeCloud, local_factory=FakeLocal)
    result = router.chat("Explain this simply.")

    assert result.provider == "local"
    assert result.text == "Local answer"


def test_local_only_reports_actual_local_error(monkeypatch) -> None:
    from app.ai.router import SmartAIRouter

    class FakeCloud:
        configured = True
        provider = "Fake Cloud"

        def chat(self, prompt, system):
            raise AssertionError("Cloud AI must not be called in Local-only mode.")

        def _protocol(self):
            return "Fake Cloud"

    class FakeLocal:
        enabled = True

        def available(self):
            return False

        def chat(self, prompt, system):
            from app.ai.local_engine import LocalAIError
            raise LocalAIError("Ollama is not running.")

    monkeypatch.setenv("AI_ROUTING_MODE", "local-only")
    router = SmartAIRouter(cloud_factory=FakeCloud, local_factory=FakeLocal)

    try:
        router.chat("Hello")
    except Exception as exc:
        assert "Ollama is not running." in str(exc)
    else:
        raise AssertionError("Expected the local error to be raised.")


def test_local_only_does_not_send_escalation_instruction(monkeypatch) -> None:
    from app.ai.router import SmartAIRouter

    class FakeCloud:
        configured = True
        provider = "Fake Cloud"

        def chat(self, prompt, system):
            raise AssertionError("Cloud AI must not be called in Local-only mode.")

        def _protocol(self):
            return "Fake Cloud"

    class FakeLocal:
        enabled = True

        def __init__(self):
            self.system = ""

        def available(self):
            return True

        def chat(self, prompt, system):
            self.system = system
            return "Hey! How can I help?"

    monkeypatch.setenv("AI_ROUTING_MODE", "local-only")
    local = FakeLocal()
    router = SmartAIRouter(cloud_factory=FakeCloud, local_factory=lambda: local)
    result = router.chat("Hey")

    assert result.provider == "local"
    assert result.text == "Hey! How can I help?"
    assert "[ESCALATE]" not in local.system


def test_local_only_never_turns_escalation_marker_into_failure(monkeypatch) -> None:
    from app.ai.router import SmartAIRouter

    class FakeCloud:
        configured = True
        provider = "Fake Cloud"

        def chat(self, prompt, system):
            raise AssertionError("Cloud AI must not be called in Local-only mode.")

        def _protocol(self):
            return "Fake Cloud"

    class FakeLocal:
        enabled = True

        def available(self):
            return True

        def chat(self, prompt, system):
            return "[ESCALATE]"

    monkeypatch.setenv("AI_ROUTING_MODE", "local-only")
    router = SmartAIRouter(cloud_factory=FakeCloud, local_factory=FakeLocal)

    result = router.chat("Hey")

    assert result.provider == "local"
    assert result.text == "I couldn't determine a reliable local answer."


def test_router_cancel_calls_provider_cancellation(monkeypatch) -> None:
    from app.ai.router import SmartAIRouter

    class FakeProvider:
        configured = True
        provider = "Fake"

        def __init__(self):
            self.cancelled = False
            self.started = False

        def begin_operation(self):
            self.started = True

        def cancel(self):
            self.cancelled = True

        def is_cancelled(self):
            return self.cancelled

        def chat(self, prompt, system):
            return "answer"

        def _protocol(self):
            return "Fake"

    monkeypatch.setenv("AI_ROUTING_MODE", "local-only")
    cloud = FakeProvider()
    local = FakeProvider()
    router = SmartAIRouter(cloud_factory=lambda: cloud, local_factory=lambda: local)

    router.begin_operation()
    router.cancel()

    assert local.started is True
    assert cloud.started is True
    assert local.cancelled is True
    assert cloud.cancelled is True
