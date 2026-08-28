"""Vision-guided desktop agent with safety-aware action permissions."""

from __future__ import annotations

import base64
import tempfile
import time
from pathlib import Path

from app.ai.provider import AIProvider
from app.agent.permissions import PermissionPolicy
from app.windows.tools import WindowsTools


class VisionAgentError(RuntimeError):
    pass


class VisionAgent:
    """Observe the screen, choose an allowed action, execute it, and continue until verified done."""

    def __init__(self, provider: AIProvider | None = None, tools: WindowsTools | None = None) -> None:
        self.provider = provider or AIProvider()
        self.tools = tools or WindowsTools()
        self.permissions = PermissionPolicy()
        self.max_steps = 12
        self._stopped = False
        self._paused = False
        self.last_steps: list[dict] = []
        self.last_goal: str = ""

    def stop(self) -> None:
        self._stopped = True

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    @property
    def pause_requested(self) -> bool:
        return self._paused

    def run(self, goal: str, progress=None) -> str:
        if not self.provider.configured:
            raise VisionAgentError("Configure a vision-capable AI provider first.")
        if not goal.strip():
            raise VisionAgentError("Please describe what you want me to do on the screen.")

        self._stopped = False
        self.last_steps = []
        self.last_goal = goal.strip()
        for step in range(1, self.max_steps + 1):
            if self._stopped:
                return "Task stopped. No further desktop actions were taken."
            while self._paused and not self._stopped:
                time.sleep(0.1)
            if self._stopped:
                return "Task stopped."

            image = self.tools.screenshot()
            decision = self._decide(goal, image)
            action = str(decision.get("action", "done")).casefold()
            message = str(decision.get("message", ""))
            self.last_steps.append(self._safe_step_record(action, decision, message))
            if progress:
                progress(f"Step {step}: {message or action}")

            if action == "done":
                return message or "Task completed."
            if action == "wait":
                time.sleep(min(max(float(decision.get("seconds", 1)), 0.2), 5.0))
                continue
            if self.permissions.requires_confirmation(action):
                return f"I paused before {action}. This action requires your confirmation before I can continue."

            self._execute_action(action, decision)
            time.sleep(0.35)

        return "I reached the maximum number of visual steps. The task was stopped to avoid uncontrolled automation."

    def _safe_step_record(self, action: str, decision: dict, message: str) -> dict:
        record = {"action": action, "message": message}
        if action in {"click", "double_click", "right_click"}:
            if "x" in decision and "y" in decision:
                record["target"] = {"x": int(decision["x"]), "y": int(decision["y"])}
        elif action == "press":
            record["key"] = str(decision.get("key", ""))
        elif action == "hotkey":
            keys = decision.get("keys", [])
            if isinstance(keys, list):
                record["keys"] = [str(k) for k in keys]
        elif action == "scroll":
            record["amount"] = int(decision.get("amount", -5))
        # Never persist text that might contain passwords or other secrets.
        return record

    def _decide(self, goal: str, image) -> dict:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
            temp_path = Path(handle.name)
        try:
            image.save(temp_path)
            encoded = base64.b64encode(temp_path.read_bytes()).decode("ascii")
        finally:
            temp_path.unlink(missing_ok=True)

        prompt = (
            "You control a Windows desktop using screenshots. Return ONLY valid JSON with one action.\n"
            "Goal: " + goal + "\n"
            "Available actions: click(x,y), double_click(x,y), right_click(x,y), type(text), "
            "press(key), hotkey(keys), scroll(amount), wait(seconds), done.\n"
            "Use coordinates in the screenshot's pixel coordinate system. Prefer the smallest next step. "
            "Never choose or attempt to bypass confirmation for send, submit, delete, purchase, upload, download, "
            "or other consequential actions. For done, include a concise message."
        )
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
