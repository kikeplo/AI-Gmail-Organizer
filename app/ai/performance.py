"""Performance helpers for a responsive desktop experience."""

from __future__ import annotations

import base64
import json
import os
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.ai.local_engine import LocalAIEngine, LocalAIError


_INSTALL_LOCK = threading.Lock()
_INSTALLED = False
_ORIGINAL_LIST_MODELS = None
_ORIGINAL_AVAILABLE = None
_ORIGINAL_RESOLVE_MODEL = None


def install_performance_optimizations() -> None:
    """Install small, process-wide optimizations without changing public APIs."""
    global _INSTALLED, _ORIGINAL_LIST_MODELS, _ORIGINAL_AVAILABLE, _ORIGINAL_RESOLVE_MODEL
    with _INSTALL_LOCK:
        if _INSTALLED:
            return
        _ORIGINAL_LIST_MODELS = LocalAIEngine.list_models
        _ORIGINAL_AVAILABLE = LocalAIEngine.available
        _ORIGINAL_RESOLVE_MODEL = LocalAIEngine.resolve_model
        LocalAIEngine.list_models = _cached_list_models  # type: ignore[method-assign]
        LocalAIEngine.available = _cached_available  # type: ignore[method-assign]
        LocalAIEngine.resolve_model = _cached_resolve_model  # type: ignore[method-assign]
        _INSTALLED = True


def _cache_state(engine: LocalAIEngine) -> dict[str, object]:
    state = getattr(LocalAIEngine, "_shared_perf_cache", None)
    if state is None:
        state = {"lock": threading.RLock(), "models": None, "expires": 0.0, "negative_until": 0.0, "url": ""}
        setattr(LocalAIEngine, "_shared_perf_cache", state)
    return state


def _cached_list_models(self: LocalAIEngine) -> list[str]:
    state = _cache_state(self)
    now = time.monotonic()
    with state["lock"]:
        if state["url"] == self.base_url and state["models"] is not None and now < float(state["expires"]):
            return list(state["models"])
        if state["url"] == self.base_url and now < float(state["negative_until"]):
            raise LocalAIError("Local AI is temporarily unavailable.")

    # Local Ollama should respond almost immediately. A short timeout prevents
    # an unavailable local runtime from adding several seconds to every command.
    if _is_local_endpoint(self.base_url):
        try:
            request = Request(f"{self.base_url}/models", headers={"Accept": "application/json"}, method="GET")
            with urlopen(request, timeout=0.8) as response:
                payload = response.read().decode("utf-8")
            data = json.loads(payload) if payload else {}
            models = [str(item["id"]) for item in data.get("data", []) if isinstance(item, dict) and item.get("id")]
            if not models:
                raise LocalAIError("No local AI models were found. Install a local model first.")
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            with state["lock"]:
                state["url"] = self.base_url
                state["models"] = None
                state["expires"] = 0.0
                state["negative_until"] = now + _negative_ttl()
            raise LocalAIError(f"Local AI health check failed: {exc}") from exc
    else:
        try:
            models = _ORIGINAL_LIST_MODELS(self)  # type: ignore[misc]
        except LocalAIError:
            with state["lock"]:
                state["url"] = self.base_url
                state["models"] = None
                state["expires"] = 0.0
                state["negative_until"] = now + _negative_ttl()
            raise

    with state["lock"]:
        state["url"] = self.base_url
        state["models"] = tuple(models)
        state["expires"] = time.monotonic() + _model_cache_ttl()
        state["negative_until"] = 0.0
    return list(models)


def _cached_available(self: LocalAIEngine) -> bool:
    if not self.enabled:
        return False
    try:
        return bool(self.list_models())
    except LocalAIError:
        return False


def _cached_resolve_model(self: LocalAIEngine) -> str:
    models = self.list_models()
    if self.model and self.model in models:
        return self.model
    blocked = ("embedding", "moderation", "image", "audio", "tts", "whisper")
    for model in models:
        if not any(token in model.lower() for token in blocked):
            return model
    return models[0]


def _is_local_endpoint(base_url: str) -> bool:
    text = base_url.lower()
    return "localhost:" in text or "127.0.0.1:" in text or "[::1]:" in text


def _model_cache_ttl() -> float:
    try:
        return max(5.0, min(float(os.getenv("LOCAL_AI_MODEL_CACHE_SECONDS", "30")), 300.0))
    except (TypeError, ValueError):
        return 30.0


def _negative_ttl() -> float:
    try:
        return max(1.0, min(float(os.getenv("LOCAL_AI_FAILURE_CACHE_SECONDS", "5")), 30.0))
    except (TypeError, ValueError):
        return 5.0


def warm_optional_imports() -> None:
    """Warm optional automation modules after the main window is visible."""
    def _warm() -> None:
        for module in ("PIL", "pyautogui", "pywinauto", "playwright"):
            try:
                __import__(module)
            except Exception:
                pass

    threading.Thread(target=_warm, name="ai-gmail-organizer-warmup", daemon=True).start()
