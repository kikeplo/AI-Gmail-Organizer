"""Fast local retrieval over saved knowledge and interaction history."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
import sqlite3

from app.memory.store import DEFAULT_DB


@dataclass(frozen=True)
class RetrievalResult:
    source: str
    title: str
    content: str
    score: float


class LocalRetriever:
    """Rank local memories using normalized token overlap and recency."""

    def __init__(self, db_path=DEFAULT_DB) -> None:
        self.db_path = db_path

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {t for t in re.findall(r"[\w@.-]+", text.casefold()) if len(t) > 2}

    @staticmethod
    def _score(query_tokens: set[str], text: str) -> float:
        doc_tokens = LocalRetriever._tokens(text)
        if not query_tokens or not doc_tokens:
            return 0.0
        overlap = len(query_tokens & doc_tokens)
        return overlap / math.sqrt(len(query_tokens) * len(doc_tokens))

    def search(self, query: str, limit: int = 8) -> list[RetrievalResult]:
        query_tokens = self._tokens(query)
        if not query_tokens:
            return []
        results: list[RetrievalResult] = []
        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT kind, title, content, updated_at FROM knowledge "
                "UNION ALL SELECT 'interaction', command, response, created_at FROM interactions "
                "ORDER BY updated_at DESC LIMIT 250"
            ).fetchall()
        for row in rows:
            text = f"{row['title']} {row['content']}"
            base = self._score(query_tokens, text)
            if base <= 0:
                continue
            results.append(RetrievalResult(str(row['kind']), str(row['title']), str(row['content']), base))
        results.sort(key=lambda item: item.score, reverse=True)
        return results[:max(1, limit)]

    def context(self, query: str, limit: int = 6, minimum_score: float = 0.16) -> str:
        results = [r for r in self.search(query, limit=limit) if r.score >= minimum_score]
        if not results:
            return ""
        lines = ["Relevant local information:", ""]
        for result in results:
            lines.append(f"• {result.title}: {result.content}")
        return "\n".join(lines)
