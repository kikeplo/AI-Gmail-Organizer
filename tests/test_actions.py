from dataclasses import dataclass

import pytest

from app.gmail.action_service import GmailActionService


@dataclass
class FakeClient:
    connected: bool = True
    archived: list[str] | None = None
    labeled: list[tuple[str, str]] | None = None

    @property
    def is_connected(self):
        return self.connected

    def _require_connection(self):
        if not self.connected:
            raise RuntimeError("not connected")

    def archive_message(self, message_id):
        if self.archived is None:
            self.archived = []
        self.archived.append(message_id)

    def apply_label(self, message_id, label_id):
        if self.labeled is None:
            self.labeled = []
        self.labeled.append((message_id, label_id))

    def list_labels(self):
        return [{"id": "L1", "name": "Work"}]

    def create_label(self, name):
        return "NEW"


def test_unconfirmed_action_never_executes():
    fake = FakeClient()
    service = GmailActionService(fake)
    action = service.plan_archive(["m1", "m2"])

    with pytest.raises(PermissionError):
        service.execute_confirmed(action, confirmed=False)

    assert fake.archived in (None, [])


def test_confirmed_archive_executes():
    fake = FakeClient()
    service = GmailActionService(fake)
    action = service.plan_archive(["m1", "m2"])

    assert service.execute_confirmed(action, confirmed=True) == 2
    assert fake.archived == ["m1", "m2"]


def test_confirmed_label_uses_existing_label():
    fake = FakeClient()
    service = GmailActionService(fake)
    action = service.plan_label(["m1"], "Work")

    assert service.execute_confirmed(action, confirmed=True) == 1
    assert fake.labeled == [("m1", "L1")]
