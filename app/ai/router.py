"""Smart local/cloud AI routing with quota cooldowns and provider failover."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
import time
from typing import Callable

from app.ai.provider import AIProvider, AIProviderError
from app.ai.local_engine import LocalAIEngine, LocalAIError


@dataclass
class ProviderState:
    name: str
    failures: int = 0
    cooldown_until: float = 0.0
    last_error: str = ""
    last_status: str = "unknown"

    @property
    def available(self) -> bool:
        return time.time() >= self.cooldown_until

    @property
    def cooldown_seconds(self) -> int:
        return max(0, int(self.cooldown_until - time.time()))


@dataclass(frozen=True)
class RouterResponse:
    text: str
    provider: str
    fallback_used: bool = False
    message: str = ""


class SmartAIRouter:
    """Select local/cloud AI, handle quota cooldowns, and fail over safely."""

    def __init__(self, cloud_factory: Callable[[], AIProvider] = AIProvider,
                 local_factory: Callable[[], LocalAIEngine] = LocalAIEngine) -> None:
        self.cloud_factory = cloud_factory
        self.local_factory = local_factory
        self.cloud = cloud_factory()
        self.local = local_factory()
        self.preference = os.getenv("AI_ROUTING_MODE", "balanced").strip().lower() or "balanced"
        self.priority = [x.strip().lower() for x in os.getenv("AI_PROVIDER_PRIORITY", "cloud,local").split(",") if x.strip()]
        self.cooldown_default = max(15, int(os.getenv("AI_QUOTA_COOLDOWN_SECONDS", "60")))
        self.states: dict[str, ProviderState] = {
            "cloud": ProviderState("Cloud AI"),
            "local": ProviderState("Local AI"),
        }

    def configured_providers(self) -> list[str]:
        result: list[str] = []
        if self.cloud.configured: result.append("cloud")
        if self.local.available(): result.append("local")
        return result

    def status(self) -> list[dict[str, str | int | bool]]:
        rows = []
        for key in ("cloud", "local"):
            state = self.states[key]
            configured = self.cloud.configured if key == "cloud" else self.local.available()
            rows.append({"provider": key, "configured": configured, "available": configured and state.available,
                          "cooldown_seconds": state.cooldown_seconds, "last_status": state.last_status,
                          "last_error": state.last_error})
        return rows

    def chat(self, prompt: str, system: str = "") -> RouterResponse:
        if self._local_first(prompt) and self.local.available():
            local = self._call_local(prompt, system)
            if local is not None: return local
        order = self._ordered_candidates()
        last_message = "No configured AI provider is available."
        for key in order:
            state = self.states[key]
            if not state.available:
                continue
            try:
                if key == "cloud":
                    if not self.cloud.configured: continue
                    text = self.cloud.chat(prompt, system)
                else:
                    if not self.local.available(): continue
                    text = self.local.chat(prompt, system)
                self._success(key)
                return RouterResponse(text=text, provider=key, fallback_used=(key != self._preferred_provider()),
                                      message=self._human_provider_message(key))
            except (AIProviderError, LocalAIError) as exc:
                last_message = str(exc)
                if self._is_quota_error(last_message) and key == "cloud":
                    self._put_on_cooldown(key, last_message)
                else:
                    self._record_failure(key, last_message)
        raise AIProviderError(last_message)

    def _call_local(self, prompt: str, system: str) -> RouterResponse | None:
        try:
            text = self.local.chat(prompt, system)
            self._success("local")
            return RouterResponse(text=text, provider="local", fallback_used=False, message="Handled locally for speed and lower cloud usage.")
        except LocalAIError as exc:
            self._record_failure("local", str(exc))
            return None

    def _ordered_candidates(self) -> list[str]:
        configured = set(self.configured_providers())
        preferred = self._preferred_provider()
        result: list[str] = []
        if preferred in configured: result.append(preferred)
        for key in self.priority:
            if key in configured and key not in result: result.append(key)
        for key in ("cloud", "local"):
            if key in configured and key not in result: result.append(key)
        return result

    def _preferred_provider(self) -> str:
        if self.preference == "local-first": return "local"
        if self.preference == "cloud-first": return "cloud"
        return self.priority[0] if self.priority else "cloud"

    def _local_first(self, prompt: str) -> bool:
        text = prompt.casefold()
        if self.preference == "cloud-first": return False
        if self.preference == "local-only": return True
        simple_terms = ("classify", "categorize", "extract", "parse", "json", "which window", "active window", "is this", "remember", "what do you remember")
        return self.preference == "local-first" or (self.preference == "balanced" and any(term in text for term in simple_terms))

    def _put_on_cooldown(self, key: str, error: str) -> None:
        state = self.states[key]
        retry = self._retry_after(error) or self.cooldown_default
        state.cooldown_until = time.time() + min(max(retry, 15), 3600)
        state.last_error = error
        state.last_status = "quota"
        state.failures += 1

    def _record_failure(self, key: str, error: str) -> None:
        state = self.states[key]
        state.failures += 1; state.last_error = error; state.last_status = "error"
        if state.failures >= 3: state.cooldown_until = time.time() + min(self.cooldown_default * state.failures, 300)

    def _success(self, key: str) -> None:
        state = self.states[key]
        state.failures = 0; state.cooldown_until = 0; state.last_error = ""; state.last_status = "available"

    @staticmethod
    def _is_quota_error(error: str) -> bool:
        text = error.casefold()
        return "429" in text or "quota" in text or "resource_exhausted" in text or "rate limit" in text or "rate_limit" in text

    @staticmethod
    def _retry_after(error: str) -> int | None:
        match = re.search(r"retry in\s+(\d+(?:\.\d+)?)s", error, re.IGNORECASE)
        if match:
            return max(1, int(float(match.group(1))))
        return None

    @staticmethod
    def _human_provider_message(key: str) -> str:
        return "Cloud AI is active." if key == "cloud" else "Local AI is active."
