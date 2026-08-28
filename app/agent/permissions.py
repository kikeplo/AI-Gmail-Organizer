"""User-friendly action permissions for autonomous desktop and browser control."""

from __future__ import annotations

from dataclasses import dataclass


SAFE_ACTIONS = {"read", "navigate", "search", "inspect", "click", "scroll", "type"}
SENSITIVE_ACTIONS = {"send", "delete", "submit", "purchase", "download", "upload"}


@dataclass(frozen=True)
class PermissionPolicy:
    """Simple policy: safe actions can run, sensitive actions require confirmation."""

    enabled: bool = True
    always_confirm_sensitive: bool = True

    def requires_confirmation(self, action: str) -> bool:
        if not self.enabled:
            return True
        return self.always_confirm_sensitive and action.casefold().strip() in SENSITIVE_ACTIONS

    def describe(self) -> str:
        return (
            "Safe actions can run automatically. Sensitive actions such as sending, deleting, "
            "submitting, purchasing, uploading, or downloading require confirmation."
        )
