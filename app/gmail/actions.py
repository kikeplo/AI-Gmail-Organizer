"""Safe Gmail action planning and execution for v0.5."""

from __future__ import annotations

from dataclasses import dataclass

from app.gmail.client import GmailClient


@dataclass(frozen=True)
class PlannedAction:
    action: str
    message_id: str
    description: str
    label_name: str | None = None


class GmailActionService:
    """Create explicit plans and execute only confirmed Gmail mutations."""

    def __init__(self, client: GmailClient | None = None) -> None:
        self.client = client or GmailClient()

    def plan_archive(self, message_ids: list[str]) -> list[PlannedAction]:
        return [
            PlannedAction("archive", message_id, f"Archive message {message_id}")
            for message_id in message_ids
        ]

    def plan_label(self, message_ids: list[str], label_name: str) -> list[PlannedAction]:
        return [
            PlannedAction(
                "label",
                message_id,
                f'Apply label "{label_name}" to message {message_id}',
                label_name=label_name,
            )
            for message_id in message_ids
        ]

    def execute(self, actions: list[PlannedAction]) -> int:
        """Execute a previously confirmed action list."""
        self.client._require_connection()
        labels: dict[str, str] = {}
        completed = 0

        for action in actions:
            if action.action == "archive":
                self.client.archive_message(action.message_id)
            elif action.action == "label":
                assert action.label_name is not None
                if action.label_name not in labels:
                    labels[action.label_name] = self._find_or_create_label(action.label_name)
                self.client.apply_label(action.message_id, labels[action.label_name])
            else:
                raise ValueError(f"Unsupported Gmail action: {action.action}")
            completed += 1
        return completed

    def _find_or_create_label(self, name: str) -> str:
        for label in self.client.list_labels():
            if label["name"].lower() == name.lower():
                return label["id"]
        return self.client.create_label(name)
