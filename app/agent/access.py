"""User-facing desktop access permissions with persistent local consent."""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock


class AccessManager:
    """Persist explicit consent for capabilities that can inspect/control the user's computer."""

    _DEFAULTS = {
        "screen": False,
        "input": False,
        "browser": False,
    }

    def __init__(self) -> None:
        self._lock = RLock()
        self._path = self._state_path()
        self._permissions = self._load()

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
            try:
                self._path.write_text(json.dumps(self._permissions, indent=2), encoding="utf-8")
            except OSError:
                pass

    def snapshot(self) -> dict[str, bool]:
        with self._lock:
            return dict(self._permissions)
