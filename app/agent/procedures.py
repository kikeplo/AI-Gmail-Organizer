"""Persistent learned procedures for reusable agent workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
import sqlite3

from app.memory.store import DEFAULT_DB


@dataclass(frozen=True)
class Procedure:
    id: int
    name: str
    goal: str
    steps: list[dict]
    successes: int
    failures: int
    updated_at: str

    @property
    def score(self) -> float:
        total = self.successes + self.failures
        return self.successes / total if total else 0.5


class ProcedureStore:
    """Store semantic, reusable agent procedures locally."""

    def __init__(self, db_path=DEFAULT_DB) -> None:
        self.db_path = db_path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS procedures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    goal TEXT NOT NULL,
                    steps_json TEXT NOT NULL,
                    successes INTEGER NOT NULL DEFAULT 0,
                    failures INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
            """)
            db.commit()

    def save(self, name: str, goal: str, steps: list[dict]) -> int:
        name = re.sub(r"\s+", " ", name.strip())
        goal = goal.strip()
        if not name or not goal or not steps:
            raise ValueError("A procedure needs a name, goal, and at least one step.")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            db.execute(
                "INSERT INTO procedures(name, goal, steps_json, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET goal=excluded.goal, steps_json=excluded.steps_json, updated_at=excluded.updated_at",
                (name, goal, json.dumps(steps, ensure_ascii=False), now),
            )
            db.commit()
            row = db.execute("SELECT id FROM procedures WHERE name=?", (name,)).fetchone()
            return int(row["id"])

    def search(self, query: str, limit: int = 5) -> list[Procedure]:
        terms = [t for t in re.findall(r"[\w@.-]+", query.casefold()) if len(t) > 2]
        with self._connect() as db:
            rows = db.execute("SELECT * FROM procedures ORDER BY updated_at DESC LIMIT 100").fetchall()
        ranked: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            text = f"{row['name']} {row['goal']}".casefold()
            overlap = sum(1 for term in terms if term in text)
            exact = 1.0 if query.casefold().strip() in text else 0.0
            confidence = int(row["successes"]) / max(1, int(row["successes"]) + int(row["failures"]))
            score = overlap + exact + confidence * 0.2
            if score > 0:
                ranked.append((score, row))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [self._from_row(row) for _, row in ranked[:max(1, limit)]]

    def record_result(self, procedure_id: int, success: bool) -> None:
        field = "successes" if success else "failures"
        with self._connect() as db:
            db.execute(f"UPDATE procedures SET {field}={field}+1, updated_at=? WHERE id=?", (datetime.now(timezone.utc).isoformat(), procedure_id))
            db.commit()

    def all(self, limit: int = 50) -> list[Procedure]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM procedures ORDER BY updated_at DESC LIMIT ?", (max(1, limit),)).fetchall()
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Procedure:
        return Procedure(
            id=int(row["id"]),
            name=str(row["name"]),
            goal=str(row["goal"]),
            steps=json.loads(row["steps_json"]),
            successes=int(row["successes"]),
            failures=int(row["failures"]),
            updated_at=str(row["updated_at"]),
        )
