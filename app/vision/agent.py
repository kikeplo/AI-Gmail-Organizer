"""Vision-guided desktop agent with automatic local fallback."""

from __future__ import annotations

import base64
import json
import tempfile
import time
from pathlib import Path

from app.ai.local_engine import LocalAIEngine, LocalAIError
from app.ai.provider import AIProvider, AIProviderError
from app.windows.tools import WindowsTools


class VisionAgentError(RuntimeError):
    pass


class VisionAgent:
    """Observe, act, and verify using cloud vision first and local vision as fallback."""

    def __init__(self, provider: AIProvider | None = None, tools: WindowsTools | None = None) -> None:
        self.provider = provider or AIProvider()
        self.tools = tools or WindowsTools()
        self.local = LocalAIEngine()
        self.max_steps = 12
        self._stopped = False
        self._paused = False
        self._last_backend = ""

    @property
    def pause_requested(self) -> bool:
        return self._paused

    def stop(self) -> None:
        self._stopped = True

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def run(self, goal: str, on_status=None) -> object:
        if not goal.strip():
            raise VisionAgentError("Please describe what you want me to do on the screen.")
        if not self.provider.configured and not self.local.available():
            raise VisionAgentError("No vision engine is available. Configure a vision-capable AI provider or install a local vision model.")

        self._stopped = False
        for step in range(1, self.max_steps + 1):
            self._wait_if_paused()
            if self._stopped:
                return self._result("Task stopped. No further desktop actions were taken.", False)

            if on_status:
                on_status(f"Looking at the screen… (step {step})")
            image = self.tools.screenshot()
            decision = self._decide(goal, image, on_status)
            action = str(decision.get("action", "done")).strip().lower()
            message = str(decision.get("message", ""))

            if on_status:
                on_status(f"Step {step}: {message or action}")
            if action == "done":
                return self._result(message or "Task completed.", False)
            if action == "wait":
                time.sleep(min(max(float(decision.get("seconds", 1)), 0.2), 5.0))
                continue
            if action in {"delete", "send", "submit", "purchase", "checkout"}:
                return self._result("I stopped before a potentially consequential action. Please perform the final action manually.", True)

            self._execute_action(action, decision)
            time.sleep(0.35)
            if on_status:
                on_status("Verifying the result…")

        return self._result("I reached the maximum number of visual steps, so I stopped safely.", False)

    def _wait_if_paused(self) -> None:
        while self._paused and not self._stopped:
            time.sleep(0.1)

    def _decide(self, goal: str, image, on_status=None) -> dict:
        prompt = (
            "You control a Windows desktop using one screenshot at a time. Return ONLY valid JSON with one action.\n"
            "Goal: " + goal + "\n"
            "Available actions: click(x,y), double_click(x,y), right_click(x,y), type(text), press(key), "
            "hotkey(keys), scroll(amount), wait(seconds), done.\n"
            "Use screenshot pixel coordinates. Choose the smallest next action. Never choose send, submit, delete, purchase, or checkout. "
            "For done, include a concise message."
        )
        if self.provider.configured:
            try:
                result = self._decide_cloud(prompt, image)
                self._last_backend = "cloud"
                return result
            except (AIProviderError, OSError) as exc:
                if on_status:
                    on_status("Cloud vision unavailable — trying local vision…")
        try:
            result = self.local.vision_json(prompt, image)
            self._last_backend = "local"
            return result
        except LocalAIError as exc:
            raise VisionAgentError(f"Vision could not analyze the screen. Cloud vision and local vision were unavailable.\n\n{exc}") from exc

    def _decide_cloud(self, prompt: str, image) -> dict:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
            temp_path = Path(handle.name)
        try:
            image.save(temp_path)
            encoded = base64.b64encode(temp_path.read_bytes()).decode("ascii")
        finally:
            temp_path.unlink(missing_ok=True)
        return self.provider.vision_json(prompt, encoded)

    def _execute_action(self, action: str, decision: dict) -> None:
        if action == "click":
            self.tools.click(int(decision["x"]), int(decision["y"]))
        elif action == "double_click":
            self.tools.double_click(int(decision["x"]), int(decision["y"]))
        elif action == "right_click":
            self.tools.click(int(decision["x"]), int(decision["y"]), button="right")
        elif action == "type":
            self.tools.type_text(str(decision.get("text", "")))
        elif action == "press":
            self.tools.press(str(decision["key"]))
        elif action == "hotkey":
            keys = decision.get("keys", [])
            if not isinstance(keys, list):
                raise VisionAgentError("Invalid hotkey plan returned by the vision model.")
            self.tools.hotkey(*[str(key) for key in keys])
        elif action == "scroll":
            self.tools.scroll(int(decision.get("amount", -5)))
        else:
            raise VisionAgentError(f"Unsupported visual action: {action}")

    @staticmethod
    def _result(text: str, needs_confirmation: bool) -> object:
        return type("VisionResult", (), {"text": text, "needs_confirmation": needs_confirmation})()
