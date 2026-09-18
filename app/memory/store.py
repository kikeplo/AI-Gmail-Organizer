"""Local interaction history and lightweight usage analytics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3


def app_data_dir() -> Path:
    root = os.getenv("LOCALAPPDATA")
    path = Path(root) / "AI Gmail Organizer" if root else Path.home() / ".ai-gmail-organizer"
    path.mkdir(parents=True, exist_ok=True)
    return path


DEFAULT_DB = app_data_dir() / "assistant.db"


@dataclass(frozen=True)
class Interaction:
    id: int
    command: str
    response: str
    mode: str
    created_at: str


class MemoryStore:
    """Persist interaction history locally on the current user's machine."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        configured = os.getenv("MEMORY_DB_PATH")
        self.db_path = Path(configured) if configured else Path(db_path or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    command TEXT NOT NULL,
                    response TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    command TEXT NOT NULL,
                    response TEXT NOT NULL,
                    rating TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def remember(self, command: str, response: str, mode: str) -> int:
        timestamp = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO interactions(command, response, mode, created_at) VALUES (?, ?, ?, ?)",
                (command, response, mode, timestamp),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def record_feedback(self, command: str, response: str, rating: str, source: str = "assistant") -> int:
        normalized = rating.strip().lower()
        if normalized not in {"up", "down"}:
            raise ValueError("Feedback rating must be 'up' or 'down'.")
        timestamp = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO ai_feedback(command, response, rating, source, created_at) VALUES (?, ?, ?, ?, ?)",
                (command, response, normalized, source, timestamp),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def recent_context(self, limit: int = 6, max_chars: int = 5000) -> str:
        """Return a compact recent conversation window for conversational AI."""
        interactions = list(reversed(self.recent(limit)))
        lines: list[str] = []
        total = 0
        for item in interactions:
            if not item.command and not item.response:
                continue
            block = f"User: {item.command}\nAssistant: {item.response}"
            remaining = max_chars - total
            if remaining <= 0:
                break
            block = block[:remaining]
            lines.append(block)
            total += len(block) + 2
        return "Recent conversation:\n\n" + "\n\n".join(lines) if lines else ""

    def recent(self, limit: int = 10) -> list[Interaction]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, command, response, mode, created_at FROM interactions ORDER BY id DESC LIMIT ?",
                (max(1, limit),),
            ).fetchall()
        return [
            Interaction(
                id=row["id"],
                command=row["command"],
                response=row["response"],
                mode=row["mode"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM interactions").fetchone()
        return int(row["total"])

    def mode_counts(self) -> dict[str, int]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT mode, COUNT(*) AS total FROM interactions GROUP BY mode ORDER BY total DESC"
            ).fetchall()
        return {str(row["mode"]): int(row["total"]) for row in rows}
