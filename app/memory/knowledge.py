"""Local-first knowledge, preferences, and reusable rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
import sqlite3
from typing import Iterable

from app.memory.store import DEFAULT_DB


@dataclass(frozen=True)
class KnowledgeItem:
    id: int
    kind: str
    title: str
    content: str
    created_at: str
    updated_at: str


class LocalKnowledge:
    """Store user rules/preferences locally and retrieve them with simple search."""

    def __init__(self, db_path=DEFAULT_DB) -> None:
        self.db_path = db_path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            connection.commit()

    def remember(self, content: str, kind: str = "memory", title: str = "") -> int:
        content = content.strip()
        if not content:
            raise ValueError("Memory cannot be empty.")
        title = title.strip() or self._make_title(content)
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO knowledge(kind, title, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (kind, title, content, now, now),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def set_preference(self, name: str, value: str) -> int:
        name = name.strip()
        value = value.strip()
        if not name or not value:
            raise ValueError("Preference name and value are required.")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT id FROM knowledge WHERE kind='preference' AND title=? ORDER BY id DESC LIMIT 1",
                (name,),
            ).fetchone()
            if existing:
                connection.execute(
                    "UPDATE knowledge SET content=?, updated_at=? WHERE id=?",
                    (value, now, existing["id"]),
                )
                connection.commit()
                return int(existing["id"])
        return self.remember(value, kind="preference", title=name)

    def search(self, query: str, limit: int = 8) -> list[KnowledgeItem]:
        terms = [term for term in re.findall(r"[\w@.-]+", query.casefold()) if len(term) > 2]
        with self._connect() as connection:
            if not terms:
                rows = connection.execute(
                    "SELECT * FROM knowledge ORDER BY updated_at DESC LIMIT ?", (max(1, limit),)
                ).fetchall()
            else:
                clauses = []
                params: list[str | int] = []
                for term in terms[:8]:
                    pattern = f"%{term}%"
                    clauses.append("(lower(title) LIKE ? OR lower(content) LIKE ?)")
                    params.extend((pattern, pattern))
                params.append(max(1, limit))
                rows = connection.execute(
                    f"SELECT * FROM knowledge WHERE {' OR '.join(clauses)} ORDER BY updated_at DESC LIMIT ?",
                    params,
                ).fetchall()
        return [KnowledgeItem(
            id=row["id"], kind=row["kind"], title=row["title"], content=row["content"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        ) for row in rows]

    def context(self, query: str, limit: int = 6) -> str:
        items = self.search(query, limit=limit)
        if not items:
            return ""
        lines = ["Relevant local knowledge:", ""]
        for item in items:
            lines.append(f"• {item.title}: {item.content}")
        return "\n".join(lines)

    def all_items(self, kind: str | None = None, limit: int = 100) -> list[KnowledgeItem]:
        with self._connect() as connection:
            if kind:
                rows = connection.execute(
                    "SELECT * FROM knowledge WHERE kind=? ORDER BY updated_at DESC LIMIT ?", (kind, max(1, limit))
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM knowledge ORDER BY updated_at DESC LIMIT ?", (max(1, limit),)
                ).fetchall()
        return [KnowledgeItem(
            id=row["id"], kind=row["kind"], title=row["title"], content=row["content"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        ) for row in rows]

    @staticmethod
    def _make_title(content: str) -> str:
        words = content.split()
        return " ".join(words[:7]).rstrip(".,:;!?—-") or "Memory"
