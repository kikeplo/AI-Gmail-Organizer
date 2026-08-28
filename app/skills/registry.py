"""Reusable skill registry for AI Gmail Organizer v2.8."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
import sqlite3
from datetime import datetime, timezone
from typing import Callable

from app.memory.store import DEFAULT_DB


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    category: str
    steps: tuple[str, ...] = field(default_factory=tuple)
    source: str = "built-in"
    enabled: bool = True


class SkillRegistry:
    """Local registry of built-in and learned semantic skills."""

    BUILT_INS = (
        Skill("Open Gmail", "Open Gmail in the browser.", "browser", ("Open Gmail",)),
        Skill("Inspect Screen", "Inspect the current screen and visible UI.", "desktop", ("Inspect the current screen",)),
        Skill("Find Unread Gmail", "Find unread Gmail messages.", "gmail", ("Search Gmail for unread messages",)),
        Skill("Open Promotions", "Open Gmail's Promotions category when visible.", "gmail", ("Open Gmail", "Find and open the Promotions tab",)),
        Skill("Archive Email", "Archive a selected or identified email after confirmation.", "gmail", ("Identify target email", "Archive the target email")),
    )

    def __init__(self, db_path=DEFAULT_DB) -> None:
        self.db_path = db_path
        self._initialize()
        self._seed_built_ins()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        return db

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS skills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    steps TEXT NOT NULL,
                    source TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    runs INTEGER NOT NULL DEFAULT 0,
                    successes INTEGER NOT NULL DEFAULT 0,
                    failures INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
            """)
            db.commit()

    def _seed_built_ins(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            for skill in self.BUILT_INS:
                db.execute(
                    "INSERT OR IGNORE INTO skills(name, description, category, steps, source, enabled, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (skill.name, skill.description, skill.category, "\n".join(skill.steps), skill.source, 1, now),
                )
            db.commit()

    def add(self, name: str, description: str, steps: list[str] | tuple[str, ...], category: str = "custom", source: str = "learned") -> Skill:
        name = name.strip()
        description = description.strip()
        clean_steps = tuple(step.strip() for step in steps if step and step.strip())
        if not name or not description or not clean_steps:
            raise ValueError("A skill needs a name, description, and at least one step.")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            db.execute(
                "INSERT INTO skills(name, description, category, steps, source, enabled, updated_at) VALUES (?, ?, ?, ?, ?, 1, ?) "
                "ON CONFLICT(name) DO UPDATE SET description=excluded.description, category=excluded.category, steps=excluded.steps, source=excluded.source, enabled=1, updated_at=excluded.updated_at",
                (name, description, category.strip() or "custom", "\n".join(clean_steps), source, now),
            )
            db.commit()
        return Skill(name, description, category.strip() or "custom", clean_steps, source, True)

    def get(self, name: str) -> Skill | None:
        normalized = name.strip().casefold()
        with self._connect() as db:
            row = db.execute("SELECT * FROM skills WHERE lower(name)=? AND enabled=1 LIMIT 1", (normalized,)).fetchone()
        return self._row_to_skill(row) if row else None

    def search(self, query: str, limit: int = 8) -> list[Skill]:
        terms = {term for term in re.findall(r"[\w-]+", query.casefold()) if len(term) > 2}
        rows = []
        with self._connect() as db:
            for row in db.execute("SELECT * FROM skills WHERE enabled=1 ORDER BY successes DESC, updated_at DESC LIMIT 200"):
                haystack = f"{row['name']} {row['description']} {row['category']} {row['steps']}".casefold()
                score = sum(1 for term in terms if term in haystack)
                if not terms or score:
                    rows.append((score, int(row["successes"]), self._row_to_skill(row)))
        rows.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in rows[:max(1, limit)]]

    def list(self, limit: int = 100) -> list[Skill]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM skills WHERE enabled=1 ORDER BY category, name LIMIT ?", (max(1, limit),)).fetchall()
        return [self._row_to_skill(row) for row in rows]

    def record_result(self, name: str, success: bool) -> None:
        column = "successes" if success else "failures"
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            db.execute(f"UPDATE skills SET runs=runs+1, {column}={column}+1, updated_at=? WHERE lower(name)=lower(?)", (now, name.strip()))
            db.commit()

    def context(self, query: str, limit: int = 4) -> str:
        skills = self.search(query, limit=limit)
        if not skills:
            return ""
        lines = ["Relevant available skills:", ""]
        for skill in skills:
            lines.append(f"• {skill.name}: {skill.description}")
            for step in skill.steps:
                lines.append(f"  → {step}")
        return "\n".join(lines)

    @staticmethod
    def _row_to_skill(row: sqlite3.Row) -> Skill:
        return Skill(
            name=str(row["name"]),
            description=str(row["description"]),
            category=str(row["category"]),
            steps=tuple(line for line in str(row["steps"]).splitlines() if line.strip()),
            source=str(row["source"]),
            enabled=bool(row["enabled"]),
        )
