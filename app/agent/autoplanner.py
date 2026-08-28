"""AI-driven task planning and execution for AI Gmail Organizer v3.0."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re

from app.agent.task_planner import TaskPlanner, TaskPlan
from app.skills.manager import SkillManager


class AutoPlannerError(RuntimeError):
    pass


@dataclass(frozen=True)
class PlannedStep:
    description: str
    skill: str = ""
    route: str = "auto"
    risk: str = "safe"


class AutoPlanner:
    """Turn a natural-language goal into a practical, safety-aware skill plan."""

    def __init__(self, task_store: TaskPlanner | None = None, skills: SkillManager | None = None) -> None:
        self.task_store = task_store or TaskPlanner()
        self.skills = skills or SkillManager()

    def plan(self, goal: str, ai=None, progress=None) -> TaskPlan:
        goal = re.sub(r"\s+", " ", goal.strip())
        if not goal:
            raise AutoPlannerError("Please describe the task you want the Organizer to complete.")

        if progress:
            progress("Creating a task plan…")

        steps = self._ai_plan(goal, ai) if ai is not None else []
        if not steps:
            steps = self._skill_plan(goal)
        if not steps:
            steps = [PlannedStep(goal)]

        if progress:
            progress(f"Plan ready: {len(steps)} step(s).")
        return self.task_store.create(goal, [
            {"description": step.description, "route": step.route, "risk": step.risk, "skill": step.skill}
            for step in steps
        ])

    def describe(self, task: TaskPlan) -> str:
        lines = [f"Task #{task.id}", task.goal, ""]
        for step in task.steps:
            marker = "✓" if step.status == "completed" else "✗" if step.status == "failed" else "•"
            lines.append(f"{marker} {step.id}. {step.description}")
        return "\n".join(lines)

    def _skill_plan(self, goal: str) -> list[PlannedStep]:
        matches = self.skills.find(goal, limit=6)
        result: list[PlannedStep] = []
        for match in matches:
            risk = "sensitive" if any(token in match.name.casefold() for token in ("send", "delete", "submit", "purchase", "upload")) else "safe"
            result.append(PlannedStep(match.name, skill=match.name, route="skill", risk=risk))
        return result

    @staticmethod
    def _ai_plan(goal: str, ai) -> list[PlannedStep]:
        if not getattr(ai, "configured", False):
            return []
        prompt = (
            "Create a concise plan for this desktop assistant goal. Return ONLY valid JSON: "
            "{\"steps\":[{\"description\":\"...\",\"route\":\"gmail_api|browser|windows|vision|local|auto\",\"risk\":\"safe|sensitive\"}]}\. "
            "Use the smallest practical steps. Mark send, delete, submit, purchase, upload, or similarly consequential actions as sensitive.\nGoal: " + goal
        )
        raw = ai.chat(prompt, "You are a task planner. Return only JSON.")
        raw = raw.replace("```json", "").replace("```", "").strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        result: list[PlannedStep] = []
        for item in data.get("steps", []) if isinstance(data, dict) else []:
            if not isinstance(item, dict):
                continue
            description = str(item.get("description", "")).strip()
            if not description:
                continue
            result.append(PlannedStep(
                description,
                route=str(item.get("route", "auto")),
                risk="sensitive" if str(item.get("risk", "safe")).casefold() == "sensitive" else "safe",
            ))
        return result[:12]
