"""Safe Gmail action planning and confirmation for v0.5."""

from __future__ import annotations

from dataclasses import dataclass

from app.gmail.client import GmailClient


@dataclass(frozen=True)
class PlannedAction:
    action: str
    message_ids: tuple[str, ...]
    description: str
    label_name: str | None = None


class GmailActionService:
    """Plan Gmail mutations and require explicit confirmation before execution."""

    def __init__(self, client: GmailClient | None = None) -> None:
        self.client = client or GmailClient()

    def plan_archive(self, message_ids: list[str]) -> PlannedAction:
        return PlannedAction(
            action="archive",
            message_ids=tuple(message_ids),
            description=f"Archive {len(message_ids)} message(s) from the inbox.",
        )

    def plan_label(self, message_ids: list[str], label_name: str) -> PlannedAction:
        return PlannedAction(
            action="label",
            message_ids=tuple(message_ids),
            description=f'Apply the "{label_name}" label to {len(message_ids)} message(s).',
            label_name=label_name,
        )

    def execute_confirmed(self, action: PlannedAction, confirmed: bool) -> int:
        """Execute only when the caller explicitly confirms the planned action."""
        if not confirmed:
            raise PermissionError("Gmail action was not confirmed by the user.")
        if not action.message_ids:
            return 0

        self.client._require_connection()
        if action.action == "archive":
            return self.client.batch_archive_messages(list(action.message_ids))

        if action.action == "label":
            if not action.label_name:
                raise ValueError("A label name is required for label actions.")
            label_id = self._find_or_create_label(action.label_name)
            for message_id in action.message_ids:
                self.client.apply_label(message_id, label_id)
            return len(action.message_ids)

        raise ValueError(f"Unsupported Gmail action: {action.action}")

    def _find_or_create_label(self, name: str) -> str:
        for label in self.client.list_labels():
            if label["name"].casefold() == name.casefold():
                return label["id"]
        return self.client.create_label(name)
