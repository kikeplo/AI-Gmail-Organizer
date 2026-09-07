"""Autonomous screenshot -> plan -> action -> verification loop."""

from __future__ import annotations

import base64
import io
import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from app.agent.access import AccessManager
from app.ai.provider import AIProvider, AIProviderError
from app.windows.tools import WindowsTools


@dataclass(frozen=True)
class VisionStep:
    action: str
    detail: str


@dataclass(frozen=True)
class VisionResult:
    text: str
    steps: tuple[VisionStep, ...] = ()
    stopped: bool = False
    needs_confirmation: bool = False


class VisionAgent:
    """Use a vision-capable model to operate the local Windows desktop iteratively."""

    def __init__(self, provider: Any | None = None, tools: WindowsTools | None = None, access: AccessManager | None = None) -> None:
        self.provider = provider or AIProvider()
        self.tools = tools or WindowsTools()
        self.access = access or AccessManager()
        self.stop_requested = False
        self.pause_requested = False
        self.last_goal: str | None = None
        self.last_steps: tuple[VisionStep, ...] = ()

    def stop(self) -> None:
        self.stop_requested = True

    def pause(self) -> None:
        self.pause_requested = True

    def resume(self) -> None:
        self.pause_requested = False

    def _provider_available(self) -> bool:
        configured = getattr(self.provider, "configured", None)
        if configured is not None:
            return bool(configured)
        configured_providers = getattr(self.provider, "configured_providers", None)
        if callable(configured_providers):
            return bool(configured_providers())
        return False

    def run(self, goal: str, max_steps: int = 20, on_status: Callable[[str], None] | None = None) -> VisionResult:
        self.stop_requested = False
        self.pause_requested = False
        self.last_goal = goal
        steps: list[VisionStep] = []
        self.last_steps = ()

        if not self._provider_available():
            raise AIProviderError("Configure an AI provider before using visual desktop control.")
        if not self.access.is_allowed("screen"):
            raise AIProviderError("Screen access is not enabled. Open Settings and allow Screen Access before asking me to look at your screen.")
        if not self.access.is_allowed("input"):
            raise AIProviderError("Mouse & keyboard access is not enabled. Open Settings and allow Mouse & Keyboard Control before asking me to control the desktop.")

        for step_number in range(1, max(1, max_steps) + 1):
            if self.stop_requested:
                self.last_steps = tuple(steps)
                return VisionResult("Task stopped.", tuple(steps), stopped=True)

            while self.pause_requested and not self.stop_requested:
                import time
                time.sleep(0.15)

            if on_status:
                on_status(f"Looking at the screen ({step_number}/{max_steps})…")

            image = self.tools.screenshot()
            image_buffer = io.BytesIO()
            image.save(image_buffer, format="PNG")
            encoded = base64.b64encode(image_buffer.getvalue()).decode("ascii")

            prompt = self._planning_prompt(goal, step_number, max_steps)
            raw = self._vision_request(prompt, encoded)
            decision = self._parse_decision(raw)

            if decision.get("done"):
                self.last_steps = tuple(steps)
                return VisionResult(decision.get("message", "Task completed."), tuple(steps))

            action = decision.get("action")
            if not isinstance(action, dict):
                raise AIProviderError("The vision model did not return a valid desktop action.")

            action_name = str(action.get("type", "")).strip().lower()
            if action_name in {"send", "delete", "trash", "empty_trash", "purchase", "submit_form"}:
                description = str(action.get("description") or action_name)
                steps.append(VisionStep("confirmation", description))
                self.last_steps = tuple(steps)
                return VisionResult(
                    f"I found a potentially consequential action: {description}. Confirm it before I continue.",
                    tuple(steps),
                    needs_confirmation=True,
                )

            detail = self._execute_action(action)
            steps.append(VisionStep(action_name, detail))
            self.last_steps = tuple(steps)
            if on_status:
                on_status(detail)

        self.last_steps = tuple(steps)
        return VisionResult("I reached the visual task step limit without confidently completing the task.", tuple(steps))

    def _vision_request(self, prompt: str, image_base64: str) -> dict | str:
        vision_json = getattr(self.provider, "vision_json", None)
        if callable(vision_json):
            return vision_json(prompt, image_base64)
        chat_with_image = getattr(self.provider, "chat_with_image", None)
        if callable(chat_with_image):
            return chat_with_image(prompt, image_base64, system_text=self._system_prompt())
        raise AIProviderError("The configured AI provider does not expose a vision interface. Choose a vision-capable provider.")

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are the visual computer-use controller for a Windows desktop assistant. "
            "Inspect the screenshot carefully and choose exactly one next action. "
            "Never invent coordinates when the target is not visible. Prefer visible UI targets. "
            "Return ONLY JSON with keys done, message, and action. "
            "When done is true, action must be null. Otherwise action must contain type and only the parameters needed."
        )

    @staticmethod
    def _planning_prompt(goal: str, step: int, max_steps: int) -> str:
        return (
            f"User goal: {goal}\n"
            f"This is visual step {step} of at most {max_steps}.\n\n"
            "Available actions:\n"
            "click {x,y}\n"
            "double_click {x,y}\n"
            "right_click {x,y}\n"
            "move {x,y}\n"
            "scroll {amount}\n"
            "type {text}\n"
            "press {key}\n"
            "hotkey {keys:[...]}\n"
            "wait {seconds}\n\n"
            "After the action, the next screenshot will be available."
        )

    @staticmethod
    def _parse_decision(raw: dict | str) -> dict:
        if isinstance(raw, dict):
            parsed = raw
        else:
            cleaned = raw.strip()
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE | re.DOTALL).strip()
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError as exc:
                raise AIProviderError("The vision model returned invalid JSON. Choose a vision-capable model and try again.") from exc
        if not isinstance(parsed, dict):
            raise AIProviderError("The vision model returned an invalid decision format.")
        return parsed

    def _execute_action(self, action: dict) -> str:
        action_name = str(action.get("type", "")).strip().lower()
        if action_name in {"click", "double_click", "right_click", "move", "scroll", "type", "press", "hotkey"} and not self.access.is_allowed("input"):
            raise AIProviderError("Mouse & keyboard access is no longer enabled. Open Settings and allow it before continuing.")
        if action_name in {"click", "double_click", "right_click", "move"}:
            x = int(action["x"]); y = int(action["y"])
            if action_name == "click": self.tools.click(x, y)
            elif action_name == "double_click": self.tools.double_click(x, y)
            elif action_name == "right_click": self.tools.click(x, y, button="right")
            else: self.tools.move_mouse(x, y)
            return f"{action_name.replace('_', ' ').title()} at ({x}, {y})."
        if action_name == "scroll":
            amount = int(action.get("amount", -5)); self.tools.scroll(amount); return f"Scrolled {amount}."
        if action_name == "type":
            self.tools.type_text(str(action.get("text", ""))); return "Entered text."
        if action_name == "press":
            key = str(action.get("key", "enter")); self.tools.press(key); return f"Pressed {key}."
        if action_name == "hotkey":
            keys = action.get("keys", [])
            if not isinstance(keys, list) or not keys: raise AIProviderError("The vision model supplied an invalid hotkey.")
            self.tools.hotkey(*[str(item) for item in keys]); return "Used a keyboard shortcut."
        if action_name == "wait":
            import time
            seconds = min(max(float(action.get("seconds", 1)), 0.1), 5.0); time.sleep(seconds); return f"Waited {seconds:.1f} seconds."
        raise AIProviderError(f"Unsupported visual action: {action_name or 'unknown'}")
