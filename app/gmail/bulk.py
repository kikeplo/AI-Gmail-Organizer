"""Natural-language bulk Gmail operations for recent-message cleanup."""

from __future__ import annotations

from dataclasses import dataclass
import re
from email.utils import parseaddr

from app.gmail.action_service import GmailActionService, PlannedAction
from app.gmail.client import GmailClient, GmailMessage


@dataclass(frozen=True)
class BulkArchivePlan:
    limit: int
    senders: tuple[str, ...]
    messages: tuple[GmailMessage, ...]
    action: PlannedAction


class BulkGmailService:
    """Resolve bounded natural-language sender cleanup into a confirmed Gmail action."""

    def __init__(self, client: GmailClient | None = None) -> None:
        self.client = client or GmailClient()
        self.actions = GmailActionService(self.client)

    @staticmethod
    def is_bulk_archive_command(command: str) -> bool:
        text = command.casefold()
        return (
            "archive" in text
            and any(term in text for term in ("recent", "last", "latest", "emails", "email"))
            and bool(re.search(r"\bfrom\b", text))
            and bool(re.search(r"\b\d{1,4}\s+emails?\b", text) or "all" in text)
        )

    def build_archive_plan(self, command: str) -> BulkArchivePlan:
        limit = self._extract_limit(command)
        senders = self._extract_senders(command)
        if not senders:
            raise ValueError("I couldn't determine which senders to archive.")
        self.client._require_connection()
        recent = self.client.list_messages(query="in:inbox", max_results=limit)
        matches = tuple(message for message in recent if self._sender_matches(message.sender, senders))
        action = self.actions.plan_archive([message.id for message in matches])
        return BulkArchivePlan(limit=limit, senders=tuple(senders), messages=matches, action=action)

    @staticmethod
    def describe(plan: BulkArchivePlan) -> str:
        names = ", ".join(plan.senders)
        count = len(plan.messages)
        if not count:
            return (
                f"I checked the {plan.limit} most recent messages in your inbox. "
                f"No messages matched: {names}. Nothing was changed."
            )
        sample = "\n".join(
            f"• {message.sender} — {message.subject}" for message in plan.messages[:8]
        )
        more = f"\n• … and {count - 8} more" if count > 8 else ""
        return (
            f"I checked the {plan.limit} most recent inbox messages and found {count} message(s) "
            f"from {names}.\n\n"
            f"They will be archived:\n{sample}{more}\n\n"
            "Nothing has been changed yet. Confirm to archive them."
        )

    @staticmethod
    def _extract_limit(command: str) -> int:
        match = re.search(r"\b(\d{1,4})\s+emails?\b", command, re.IGNORECASE)
        if match:
            return max(1, min(int(match.group(1)), 500))
        return 500

    @staticmethod
    def _extract_senders(command: str) -> list[str]:
        match = re.search(r"\bfrom\s+(.+)$", command, re.IGNORECASE)
        if not match:
            return []
        text = match.group(1).strip().rstrip(". ")
        text = re.sub(r"\b(and\s+)?(?:archive|archived|then\s+archive)\b.*$", "", text, flags=re.IGNORECASE).strip(" ,")
        text = re.sub(r"^(?:all|all emails|all the emails)\s+", "", text, flags=re.IGNORECASE).strip()
        parts = re.split(r"\s*(?:,|\band\b|&|\bor\b)\s*", text, flags=re.IGNORECASE)
        return [p.strip(" \"'") for p in parts if p.strip(" \"'")]

    @classmethod
    def _sender_matches(cls, sender: str, requested: list[str] | tuple[str, ...]) -> bool:
        display_name, address = parseaddr(sender)
        display = cls._normalize(display_name)
        email = cls._normalize(address)
        domain = email.split("@", 1)[1] if "@" in email else ""
        for requested_sender in requested:
            value = cls._normalize(requested_sender)
            if not value:
                continue
            if "@" in value:
                if email == value:
                    return True
            elif "." in value and value in domain:
                return True
            elif value == display or value == email:
                return True
        return False

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip().strip('"\'')).casefold()
