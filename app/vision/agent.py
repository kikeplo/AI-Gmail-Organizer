"""Vision-guided desktop agent with explicit screen/input consent and AI failover."""

from __future__ import annotations

import base64
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from app.ai.router import SmartAIRouter
from app.agent.access import AccessManager
from app.agent.permissions import PermissionPolicy
from app.windows.tools import WindowsTools


class VisionAgentError(RuntimeError):
    pass


@dataclass(frozen=True)
class VisionResult:
    """Structured result consumed by the command router and UI."""

    text: str
    stopped: bool = False
    needs_confirmation: bool = False
    steps: list[dict] | None = None


class VisionAgent:
    """Observe the screen, choose an allowed action, and stop safely."""

    def __init__(self, router: SmartAIRouter | None = None, tools: WindowsTools | None = None) -> None:
        self.router = router or SmartAIRouter()
        self.tools = tools or WindowsTools()
        self.permissions = PermissionPolicy()
        self.access = AccessManager()
        self.max_steps = 12
        self._stopped = False
        self._paused = False
        self.last_steps: list[dict] = []
        self.last_goal: str = ""
        self._screenshot_size: tuple[int, int] | None = None

    def stop(self) -> None:
        self._stopped = True

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    @property
    def pause_requested(self) -> bool:
        return self._paused

    def ensure_access(self) -> None:
        """Local Windows automation is enabled without an in-app permission dialog."""
        return

    def run(self, goal: str, progress=None) -> VisionResult:
        if not self.router.cloud.configured and not self.router.local.available():
            raise VisionAgentError("Configure a vision-capable AI provider or install a local vision model first.")
        if not goal.strip():
            raise VisionAgentError("Please describe what you want me to do on the screen.")
        self.ensure_access()

        self._stopped = False
        self.last_steps = []
        self.last_goal = goal.strip()
        explicit_single_click = bool(re.match(r"^\s*(?:click|double[- ]click|right[- ]click)\b", goal, re.IGNORECASE))
        recent_actions: list[str] = []

        for step in range(1, self.max_steps + 1):
            if self._stopped:
                return VisionResult("Task stopped. No further desktop actions were taken.", stopped=True, steps=list(self.last_steps))
            while self._paused and not self._stopped:
                time.sleep(0.1)
            if self._stopped:
                return VisionResult("Task stopped.", stopped=True, steps=list(self.last_steps))

            image = self.tools.screenshot()
            self._screenshot_size = tuple(int(value) for value in image.size)
            decision = self._decide(goal, image)
            action = str(decision.get("action", "done")).casefold()
            message = str(decision.get("message", ""))

            action_key = self._action_fingerprint(action, decision)
            if action_key in recent_actions[-2:]:
                return VisionResult(
                    "I stopped because the same visual action was being repeated without verified progress.",
                    stopped=True,
                    steps=list(self.last_steps),
                )
            recent_actions.append(action_key)

            self.last_steps.append(self._safe_step_record(action, decision, message))
            if progress:
                progress(f"Step {step}: {message or action}")
            if action == "done":
                return VisionResult(message or "Task completed.", steps=list(self.last_steps))
            if action == "wait":
                time.sleep(min(max(float(decision.get("seconds", 1)), 0.2), 5.0))
                continue
            if self.permissions.requires_confirmation(action):
                return VisionResult(
                    f"I paused before {action}. This action requires your confirmation before I can continue.",
                    needs_confirmation=True,
                    steps=list(self.last_steps),
                )
            self._execute_action(action, decision)

            if explicit_single_click and action in {"click", "double_click", "right_click"}:
                return VisionResult(message or f"Completed: {goal.strip()}", steps=list(self.last_steps))
            time.sleep(0.35)

        return VisionResult(
            "I reached the maximum number of visual steps. The task was stopped to avoid uncontrolled automation.",
            stopped=True,
            steps=list(self.last_steps),
        )

    @staticmethod
    def _action_fingerprint(action: str, decision: dict) -> str:
        if action in {"click", "double_click", "right_click"}:
            target = VisionAgent._raw_target_point(decision)
            if target is not None:
                x, y = target
                return f"{action}:{x // 12}:{y // 12}"
        return action

    def _safe_step_record(self, action: str, decision: dict, message: str) -> dict:
        record = {"action": action, "message": message}
        target = self._target_point(decision)
        if action in {"click", "double_click", "right_click"} and target is not None:
            record["target"] = {"x": target[0], "y": target[1]}
        elif action == "press":
            record["key"] = str(decision.get("key", ""))
        elif action == "hotkey":
            keys = decision.get("keys", [])
            if isinstance(keys, list):
                record["keys"] = [str(k) for k in keys]
        elif action == "scroll":
            record["amount"] = int(decision.get("amount", -5))
        return record

    @staticmethod
    def _raw_target_point(decision: dict) -> tuple[float, float] | None:
        bbox = decision.get("bbox")
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            try:
                x1, y1, x2, y2 = [float(value) for value in bbox]
                return (x1 + x2) / 2.0, (y1 + y2) / 2.0
            except (TypeError, ValueError):
                pass
        if "x" in decision and "y" in decision:
            try:
                return float(decision["x"]), float(decision["y"])
            except (TypeError, ValueError):
                return None
        return None

    def _target_point(self, decision: dict) -> tuple[int, int] | None:
        target = self._raw_target_point(decision)
        if target is None:
            return None
        x, y = target
        ratio_x, ratio_y = self._get_coordinate_ratio()
        return round(x * ratio_x), round(y * ratio_y)

    def _get_coordinate_ratio(self) -> tuple[float, float]:
        if not self._screenshot_size:
            return 1.0, 1.0
        try:
            import pyautogui
            screen_w, screen_h = pyautogui.size()
            shot_w, shot_h = self._screenshot_size
            if shot_w > 0 and shot_h > 0 and screen_w > 0 and screen_h > 0:
                return screen_w / shot_w, screen_h / shot_h
        except Exception:
            pass
        return 1.0, 1.0

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
            "Available actions: click, double_click, right_click, type, press, hotkey, scroll, wait, done.\n"
            "For click/double_click/right_click, prefer a bbox field [left, top, right, bottom] for the exact visible target and use its center; "
            "only use x/y when a bounding box is not possible. Coordinates must be expressed in the screenshot's pixel coordinate system, not browser/CSS coordinates.\n"
            "After an explicit single click request has been successfully executed, return done rather than requesting another click.\n"
            "For a multi-step goal, after each action inspect the new screenshot and return done as soon as the requested end state is visibly achieved. "
            "Never repeat an identical click unless the screen visibly changed and the repeat is necessary. "
            "Prefer the smallest next step. Never choose or attempt to bypass confirmation for send, submit, delete, purchase, upload, download, "
            "or other consequential actions. For done, include a concise message."
        )
        return self.router.vision_json(prompt, encoded)

    def _execute_action(self, action: str, decision: dict) -> None:
        if action in {"click", "double_click", "right_click"}:
            target = self._target_point(decision)
            if target is None:
                raise VisionAgentError("The vision model did not provide a valid click target.")
            x, y = target
            if action == "click":
                self.tools.click(x, y)
            elif action == "double_click":
                self.tools.double_click(x, y)
            else:
                self.tools.click(x, y, button="right")
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
