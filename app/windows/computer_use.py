"""Vision-guided Windows computer-use loop for AI Gmail Organizer."""

from __future__ import annotations

import base64
import io
import json
import re
import time
from dataclasses import dataclass

from app.ai.provider import AIProvider, AIProviderError
from app.windows.tools import WindowsTools


@dataclass(frozen=True)
class ComputerAction:
    action: str
    x: int | None = None
    y: int | None = None
    text: str = ""
    key: str = ""
    keys: tuple[str, ...] = ()
    clicks: int = 1
    button: str = "left"
    scroll: int = 0
    reason: str = ""


class ComputerUseError(RuntimeError):
    pass


class VisionComputerUse:
    """Capture the screen, ask the configured vision model for one action, execute it, and repeat."""

    MAX_STEPS = 12

    def __init__(self, ai: AIProvider | None = None, tools: WindowsTools | None = None) -> None:
        self.ai = ai or AIProvider()
        self.tools = tools or WindowsTools()

    def run(self, goal: str, max_steps: int | None = None) -> str:
        if not self.ai.configured:
            raise ComputerUseError("Configure an AI provider before using visual desktop control.")
        steps = min(max_steps or self.MAX_STEPS, self.MAX_STEPS)
        history: list[str] = []
        for step in range(1, steps + 1):
            image = self.tools.screenshot()
            decision = self._decide(goal, image, history, step, steps)
            action = self._parse_action(decision)
            if action.action == "done":
                return action.reason or "The requested desktop task is complete."
            if action.action == "ask":
                return action.reason or "I need your input before continuing."
            self._execute(action)
            history.append(self._describe(action))
            time.sleep(0.5)
        return "I reached the visual-control step limit before confirming completion."

    def _decide(self, goal: str, image, history: list[str], step: int, total: int) -> str:
        data = io.BytesIO()
        image.save(data, format="PNG")
        encoded = base64.b64encode(data.getvalue()).decode("ascii")
        prompt = (
            "You are controlling a Windows desktop for the user. Analyze the screenshot and choose exactly ONE next action. "
            "Use screen coordinates measured from the screenshot, not guesses. Never claim success unless the screenshot confirms it. "
            "Avoid destructive actions such as deleting emails, sending messages, purchasing, or submitting forms unless the user's goal explicitly requires it. "
            "Return ONLY valid JSON, no Markdown.\n\n"
            f"Goal: {goal}\n"
            f"Step: {step}/{total}\n"
            f"Previous actions: {json.dumps(history[-8:])}\n\n"
            "Allowed JSON actions:\n"
            '{"action":"click","x":123,"y":456,"button":"left"}\n'
            '{"action":"double_click","x":123,"y":456}\n'
            '{"action":"right_click","x":123,"y":456}\n'
            '{"action":"move","x":123,"y":456}\n'
            '{"action":"type","text":"..."}\n'
            '{"action":"press","key":"enter"}\n'
            '{"action":"hotkey","keys":["ctrl","l"]}\n'
            '{"action":"scroll","scroll":-5}\n'
            '{"action":"done","reason":"..."}\n'
            '{"action":"ask","reason":"..."}\n'
        )
        return self.ai.chat_with_image(prompt, encoded, "You are a careful Windows computer-use agent.")

    @staticmethod
    def _parse_action(response: str) -> ComputerAction:
        cleaned = response.strip()
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE | re.DOTALL).strip()
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ComputerUseError("The vision model returned invalid control instructions.") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("action"), str):
            raise ComputerUseError("The vision model returned an invalid control action.")
        action = payload["action"].lower().strip()
        return ComputerAction(
            action=action,
            x=int(payload["x"]) if payload.get("x") is not None else None,
            y=int(payload["y"]) if payload.get("y") is not None else None,
            text=str(payload.get("text", "")),
            key=str(payload.get("key", "")),
            keys=tuple(str(k) for k in payload.get("keys", [])),
            clicks=int(payload.get("clicks", 1)),
            button=str(payload.get("button", "left")),
            scroll=int(payload.get("scroll", 0)),
            reason=str(payload.get("reason", "")),
        )

    def _execute(self, action: ComputerAction) -> None:
        if action.action == "click":
            self.tools.click(action.x, action.y, button=action.button, clicks=action.clicks)
        elif action.action == "double_click":
            self.tools.double_click(action.x, action.y)
        elif action.action == "right_click":
            self.tools.click(action.x, action.y, button="right")
        elif action.action == "move":
            if action.x is None or action.y is None:
                raise ComputerUseError("Move action is missing coordinates.")
            self.tools.move_mouse(action.x, action.y)
        elif action.action == "type":
            self.tools.type_text(action.text)
        elif action.action == "press":
            self.tools.press(action.key)
        elif action.action == "hotkey":
            self.tools.hotkey(*action.keys)
        elif action.action == "scroll":
            self.tools.scroll(action.scroll)
        else:
            raise ComputerUseError(f"Unsupported visual action: {action.action}")

    @staticmethod
    def _describe(action: ComputerAction) -> str:
        if action.action in {"click", "double_click", "right_click", "move"}:
            return f"{action.action} at ({action.x}, {action.y})"
        if action.action == "type":
            return f"type {len(action.text)} characters"
        if action.action == "press":
            return f"press {action.key}"
        if action.action == "hotkey":
            return f"hotkey {'+'.join(action.keys)}"
        if action.action == "scroll":
            return f"scroll {action.scroll}"
        return action.action
