"""Skill orchestration helpers for AI Gmail Organizer v2.8."""

from __future__ import annotations

from dataclasses import dataclass

from app.skills.registry import Skill, SkillRegistry


@dataclass(frozen=True)
class SkillMatch:
    skill: Skill
    confidence: float


class SkillManager:
    """Discover, compose, and track reusable skills without executing actions itself."""

    def __init__(self, db_path) -> None:
        self.registry = SkillRegistry(db_path)

    def discover(self, request: str, limit: int = 5) -> list[SkillMatch]:
        matches = self.registry.search(request, limit=limit)
        query_terms = {word.casefold() for word in request.split() if len(word) > 2}
        output: list[SkillMatch] = []
        for skill in matches:
            haystack = f"{skill.name} {skill.description} {' '.join(skill.steps)}".casefold()
            overlap = sum(1 for term in query_terms if term in haystack)
            confidence = min(1.0, 0.25 + overlap / max(4, len(query_terms)))
            output.append(SkillMatch(skill, confidence))
        return output

    def plan(self, request: str, limit: int = 3) -> list[Skill]:
        return [match.skill for match in self.discover(request, limit=limit) if match.confidence >= 0.35]

    def describe(self, request: str, limit: int = 5) -> str:
        matches = self.discover(request, limit=limit)
        if not matches:
            return "No reusable skill matched this request."
        lines = ["Relevant skills", ""]
        for match in matches:
            lines.append(f"• {match.skill.name} — {match.skill.description}")
            lines.append(f"  Match: {match.confidence:.0%}")
        return "\n".join(lines)

    def record_success(self, name: str) -> None:
        self.registry.record_result(name, True)

    def record_failure(self, name: str) -> None:
        self.registry.record_result(name, False)
