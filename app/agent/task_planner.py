"""Multi-step local task planning for AI Gmail Organizer."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import re
import sqlite3

from app.memory.store import DEFAULT_DB


@dataclass(frozen=True)
class TaskStep:
    id: int
    description: str
    route: str = "auto"
    status: str = "pending"
    attempts: int = 0
    result: str = ""


@dataclass(frozen=True)
class TaskPlan:
    id: int
    goal: str
    status: str
    steps: list[TaskStep]
    created_at: str
    updated_at: str


class TaskPlanner:
    """Persist lightweight task plans and track each step independently."""

    def __init__(self, db_path=DEFAULT_DB) -> None:
        self.db_path = db_path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        return db

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS task_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal TEXT NOT NULL,
                status TEXT NOT NULL,
                steps_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""")
            db.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create(self, goal: str, steps: list[str | dict]) -> TaskPlan:
        goal = re.sub(r"\s+", " ", goal.strip())
        normalized: list[dict] = []
        for index, step in enumerate(steps, start=1):
            if isinstance(step, str):
                normalized.append(asdict(TaskStep(index, step.strip())))
            else:
                normalized.append(asdict(TaskStep(
                    index,
                    str(step.get("description", "")).strip(),
                    str(step.get("route", "auto")),
                )))
        normalized = [item for item in normalized if item["description"]]
        if not goal or not normalized:
            raise ValueError("A task needs a goal and at least one step.")
        now = self._now()
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO task_plans(goal,status,steps_json,created_at,updated_at) VALUES(?,?,?,?,?)",
                (goal, "pending", json.dumps(normalized, ensure_ascii=False), now, now),
            )
            task_id = int(cursor.lastrowid)
            db.commit()
        return self.get(task_id)

    def get(self, task_id: int) -> TaskPlan:
        with self._connect() as db:
            row = db.execute("SELECT * FROM task_plans WHERE id=?", (task_id,)).fetchone()
        if not row:
            raise KeyError(f"Task {task_id} was not found.")
        raw_steps = json.loads(row["steps_json"])
        steps = [TaskStep(**item) for item in raw_steps]
        return TaskPlan(int(row["id"]), str(row["goal"]), str(row["status"]), steps, str(row["created_at"]), str(row["updated_at"]))

    def latest(self) -> TaskPlan | None:
        with self._connect() as db:
            row = db.execute("SELECT id FROM task_plans ORDER BY id DESC LIMIT 1").fetchone()
        return self.get(int(row["id"])) if row else None

    def update_step(self, task_id: int, step_id: int, status: str, result: str = "") -> TaskPlan:
        task = self.get(task_id)
        steps = []
        for step in task.steps:
            if step.id == step_id:
                steps.append(TaskStep(step.id, step.description, step.route, status, step.attempts + 1, result))
            else:
                steps.append(step)
        overall = "running"
        if any(step.status == "blocked" for step in steps): overall = "blocked"
        elif all(step.status == "completed" for step in steps): overall = "completed"
        elif any(step.status == "failed" for step in steps) and not any(step.status == "pending" for step in steps): overall = "failed"
        with self._connect() as db:
            db.execute("UPDATE task_plans SET status=?, steps_json=?, updated_at=? WHERE id=?", (overall, json.dumps([asdict(s) for s in steps], ensure_ascii=False), self._now(), task_id))
            db.commit()
        return self.get(task_id)

    def cancel(self, task_id: int) -> TaskPlan:
        with self._connect() as db:
            db.execute("UPDATE task_plans SET status='cancelled', updated_at=? WHERE id=?", (self._now(), task_id))
            db.commit()
        return self.get(task_id)
