"""Local capability state for desktop automation.

Desktop automation is intentionally enabled by default for this local-only app.
The application does not display a separate permission dialog; Windows/PyAutoGUI
controls access at the OS/session level.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock


class AccessManager:
    """Persist local capability state without blocking visual automation."""

    _DEFAULTS = {
        "screen": True,
        "input": True,
        "browser": True,
    }

    def __init__(self) -> None:
        self._lock = RLock()
        self._path = self._state_path()
        self._permissions = self._load()
        # Existing installs may contain the old all-false defaults. Treat missing
        # capabilities as enabled so upgrading does not leave visual control blocked.
        changed = False
        for key, default in self._DEFAULTS.items():
            if key not in self._permissions:
                self._permissions[key] = default
                changed = True
        if changed:
            self._save()

    @staticmethod
    def _state_path() -> Path:
        root = os.getenv("APPDATA") or os.getenv("LOCALAPPDATA") or str(Path.home())
        path = Path(root) / "AI-Gmail-Organizer"
        path.mkdir(parents=True, exist_ok=True)
        return path / "permissions.json"

    def _load(self) -> dict[str, bool]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return {key: bool(data.get(key, default)) for key, default in self._DEFAULTS.items()}
        except (OSError, ValueError, TypeError):
            return dict(self._DEFAULTS)

    def _save(self) -> None:
        try:
            self._path.write_text(json.dumps(self._permissions, indent=2), encoding="utf-8")
        except OSError:
            pass

    def is_allowed(self, capability: str) -> bool:
        with self._lock:
            return bool(self._permissions.get(capability, False))

    def grant(self, capability: str) -> None:
        self._set(capability, True)

    def revoke(self, capability: str) -> None:
        self._set(capability, False)

    def _set(self, capability: str, value: bool) -> None:
        if capability not in self._DEFAULTS:
            raise ValueError(f"Unknown capability: {capability}")
        with self._lock:
            self._permissions[capability] = value
            self._save()

    def snapshot(self) -> dict[str, bool]:
        with self._lock:
            return dict(self._permissions)
