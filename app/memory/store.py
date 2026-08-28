"""Local memory and lightweight analytics for AI Gmail Organizer v0.7."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from datetime import datetime, timezone
import os

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB = BASE_DIR / "data" / "assistant.db"


@dataclass(frozen=True)
class Interaction:
    id: int
    command: str
    response: str
    mode: str
    created_at: str


class MemoryStore:
    """Persist local interaction history without sending it to a remote service."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        configured = os.getenv("MEMORY_DB_PATH")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
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
