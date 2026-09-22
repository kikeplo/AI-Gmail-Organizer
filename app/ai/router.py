"""Smart local/cloud AI routing with provider failover and automatic escalation."""

from __future__ import annotations

from dataclasses import dataclass
import base64
import json
import os
import re
import time
from io import BytesIO
from typing import Callable

from app.ai.provider import AIProvider, AIProviderError
from app.ai.local_engine import LocalAIEngine, LocalAIError, LocalAICancelled


@dataclass
class ProviderState:
    name: str
    requests: int = 0
    successes: int = 0
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
    """Prefer local AI for normal work, with explicit cloud escalation unless Local-only is selected."""

    def __init__(self, cloud_factory: Callable[[], AIProvider] = AIProvider,
                 local_factory: Callable[[], LocalAIEngine] = LocalAIEngine) -> None:
        self.cloud = cloud_factory()
        self.local = local_factory()
        self.preference = os.getenv("AI_ROUTING_MODE", "local-first").strip().lower() or "local-first"
        self.priority = [x.strip().lower() for x in os.getenv("AI_PROVIDER_PRIORITY", "local,cloud").split(",") if x.strip()]
        self.cooldown_default = max(15, int(os.getenv("AI_QUOTA_COOLDOWN_SECONDS", "60")))
        self.states = {"cloud": ProviderState("Cloud AI"), "local": ProviderState("Local AI")}

    def begin_operation(self) -> None:
        """Reset cancellation state for a new top-level assistant command."""
        begin = getattr(self.local, "begin_operation", None)
        if callable(begin):
            begin()
        begin = getattr(self.cloud, "begin_operation", None)
        if callable(begin):
            begin()

    def cancel(self) -> None:
        """Interrupt active local/cloud provider requests immediately."""
        cancel = getattr(self.local, "cancel", None)
        if callable(cancel):
            cancel()
        cancel = getattr(self.cloud, "cancel", None)
        if callable(cancel):
            cancel()

    def is_cancelled(self) -> bool:
        return bool(
            getattr(self.local, "is_cancelled", lambda: False)()
            or getattr(self.cloud, "is_cancelled", lambda: False)()
        )


    def _routing_mode(self) -> str:
        """Read routing mode at request time so saved Settings take effect without restarting the app."""
        mode = os.getenv("AI_ROUTING_MODE", self.preference).strip().lower() or self.preference
        if mode in {"local-first", "cloud-first", "balanced", "local-only"}:
            self.preference = mode
        return self.preference

    def _local_only(self) -> bool:
        return self._routing_mode() == "local-only"

    def configured_providers(self) -> list[str]:
        result = []
        if not self._local_only() and self.cloud.configured:
            result.append("cloud")
        if self.local.available():
            result.append("local")
        return result

    def status(self) -> list[dict[str, str | int | bool]]:
        rows = []
        names = {"cloud": self.cloud.provider or self.cloud._protocol(), "local": "Local AI"}
        local_only = self._local_only()
        for key in ("cloud", "local"):
            state = self.states[key]
            if key == "cloud":
                configured = self.cloud.configured and not local_only
            else:
                configured = self.local.available()
            rows.append({"provider": names[key], "configured": configured, "available": configured and state.available,
                          "cooldown_seconds": state.cooldown_seconds, "last_status": state.last_status,
                          "last_error": state.last_error, "requests": state.requests,
                          "successes": state.successes, "failures": state.failures})
        return rows

    def chat(self, prompt: str, system: str = "") -> RouterResponse:
        """Run through local AI first when selected; Local-only never contacts cloud AI."""
        self._check_cancelled()
        last_message = "No configured AI provider is available."
        attempted_local = False
        local_only = self._local_only()

        if local_only:
            # Local-only must attempt the local engine directly so a stopped
            # runtime or missing model produces the real local error instead
            # of the generic "unavailable" message.
            attempted_local = True
            local = self._call_local(prompt, system)
            if local is not None:
                return local
            self._check_cancelled()
            last_message = self.states["local"].last_error or last_message
            if not last_message:
                try:
                    last_message = str(self.local.status().get("reason", "")).strip()
                except Exception:
                    pass
            raise AIProviderError(last_message or "Local AI is required, but it is unavailable.")

        if self._local_first(prompt) and self.local.available():
            attempted_local = True
            local = self._call_local(prompt, system)
            if local is not None:
                return local
            last_message = self.states["local"].last_error or last_message

        if self._is_complex_prompt(prompt):
            candidates = ["cloud"] if self.cloud.configured else []
            candidates.append("local")
        else:
            candidates = self._ordered_candidates(skip_local=attempted_local)

        for key in candidates:
            state = self.states[key]
            if not state.available:
                continue
            try:
                state.requests += 1
                if key == "cloud":
                    if not self.cloud.configured:
                        continue
                    text = self.cloud.chat(prompt, system)
                else:
                    if not self.local.available():
                        continue
                    text = self.local.chat(prompt, system)
                self._success(key)
                fallback = attempted_local and key == "cloud"
                message = "Local AI was unavailable or escalated, so Cloud AI handled this request." if fallback else self._human_provider_message(key)
                return RouterResponse(text, key, fallback, message)
            except (AIProviderError, LocalAIError) as exc:
                last_message = str(exc)
                if self._is_quota_error(last_message) and key == "cloud":
                    self._put_on_cooldown(key, last_message)
                else:
                    self._record_failure(key, last_message)

        raise AIProviderError(last_message)

    def vision_json(self, prompt: str, image_base64: str) -> dict:
        """Run vision through the same provider failover rules; Local-only never contacts cloud AI."""
        last_message = "No configured vision-capable AI provider is available."
        candidates = self._ordered_candidates()
        if self._local_only():
            candidates = [key for key in candidates if key == "local"]
        for key in candidates:
            state = self.states[key]
            if not state.available:
                continue
            try:
                state.requests += 1
                if key == "cloud":
                    if not self.cloud.configured:
                        continue
                    result = self.cloud.vision_json(prompt, image_base64)
                else:
                    if not self.local.available():
                        continue
                    from PIL import Image
                    image = Image.open(BytesIO(base64.b64decode(image_base64)))
                    result = self.local.vision_json(prompt, image)
                self._success(key)
                return result
            except (AIProviderError, LocalAIError) as exc:
                last_message = str(exc)
                if self._is_quota_error(last_message) and key == "cloud":
                    self._put_on_cooldown(key, last_message)
                else:
                    self._record_failure(key, last_message)
        raise AIProviderError(last_message)

    def classify_json(self, payload: list[dict], system: str = "") -> list[dict]:
        """Use local-first structured output and escalate only when cloud routing is permitted."""
        result = self.chat(json.dumps(payload), system)
        parsed = self._parse_json_list(result.text)
        if parsed is not None:
            return parsed
        if result.provider == "local" and self.cloud.configured and not self._local_only():
            cloud = self._cloud_chat(json.dumps(payload), system)
            parsed = self._parse_json_list(cloud.text)
            if parsed is not None:
                return parsed
        raise AIProviderError("The AI provider did not return valid JSON for classification.")

    def _cloud_chat(self, prompt: str, system: str = "") -> RouterResponse:
        if self._local_only():
            raise AIProviderError("Cloud AI is disabled by Local-only routing.")
        last_error = "Cloud AI is unavailable."
        state = self.states["cloud"]
        if not state.available or not self.cloud.configured:
            raise AIProviderError(last_error)
        try:
            state.requests += 1
            text = self.cloud.chat(prompt, system)
            self._success("cloud")
            return RouterResponse(text, "cloud", True, "Local AI could not produce the required structured result, so Cloud AI handled it.")
        except AIProviderError as exc:
            last_error = str(exc)
            if self._is_quota_error(last_error):
                self._put_on_cooldown("cloud", last_error)
            else:
                self._record_failure("cloud", last_error)
            raise AIProviderError(last_error) from exc

    @staticmethod
    def _parse_json_list(text: str) -> list[dict] | None:
        cleaned = text.replace("```json", "").replace("```", "").strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, list) and all(isinstance(item, dict) for item in parsed) else None

    def _call_local(self, prompt: str, system: str) -> RouterResponse | None:
        try:
            self.states["local"].requests += 1
            base_system = system or "You are the local AI assistant for AI Gmail Organizer."

            # Local-only mode has nowhere to escalate. Do not give the model
            # an escalation sentinel in this mode, because simple requests can
            # otherwise produce [ESCALATE] and be incorrectly treated as a failure.
            if self._local_only():
                local_system = (
                    base_system
                    + "\nAnswer the user's request directly with the best answer you can. "
                    "Do not output an escalation marker and do not claim external actions occurred."
                )
            else:
                local_system = (
                    base_system
                    + "\nIf you cannot reliably solve the request with your available knowledge, "
                    "return exactly [ESCALATE] and nothing else. Do not pretend an external action occurred."
                )

            text = self.local.chat(prompt, local_system)
            if text.strip().upper().startswith("[ESCALATE]"):
                if self._local_only():
                    # A local model should still never trigger cloud routing
                    # from Local-only mode. Preserve any useful text after a
                    # malformed marker; otherwise ask it to answer directly.
                    cleaned = re.sub(r"^\s*\[ESCALATE\]\s*", "", text, flags=re.IGNORECASE).strip()
                    if cleaned:
                        self._success("local")
                        return RouterResponse(cleaned, "local", False, "Handled by the local AI for privacy and speed.")
                    text = "I couldn't determine a reliable local answer."
                else:
                    self.states["local"].last_error = "Local AI requested cloud escalation."
                    self.states["local"].last_status = "escalated"
                    return None

            self._success("local")
            return RouterResponse(text, "local", False, "Handled by the local AI for privacy and speed.")
        except LocalAICancelled:
            self.states["local"].last_status = "cancelled"
            self.states["local"].last_error = "Local AI request stopped."
            return None
        except LocalAIError as exc:
            self._record_failure("local", str(exc))
            return None

    def _check_cancelled(self) -> None:
        if self.is_cancelled():
            raise AIProviderError("AI request stopped by user.")

    def _ordered_candidates(self, *, skip_local: bool = False) -> list[str]:
        configured = set(self.configured_providers())
        preferred = self._preferred_provider()
        result: list[str] = []
        if preferred in configured and not (skip_local and preferred == "local"):
            result.append(preferred)
        for key in self.priority:
            if key in configured and key not in result and not (skip_local and key == "local"):
                result.append(key)
        for key in ("local", "cloud"):
            if key in configured and key not in result and not (skip_local and key == "local"):
                result.append(key)
        return result

    def _preferred_provider(self) -> str:
        mode = self._routing_mode()
        if mode == "local-first":
            return "local"
        if mode == "cloud-first":
            return "cloud"
        return self.priority[0] if self.priority else "local"

    @staticmethod
    def _is_complex_prompt(prompt: str) -> bool:
        """Detect prompts that benefit from a larger cloud reasoning model."""
        text = prompt.casefold().strip()
        if not text:
            return False
        words = re.findall(r"\b\w+\b", text)
        if len(words) >= 140 or "```" in text:
            return True
        complex_terms = (
            "deeply", "in depth", "in-depth", "detailed analysis", "comprehensive",
            "research", "compare", "comparison", "trade-off", "tradeoff", "architecture",
            "debug", "debugging", "write code", "implement", "refactor", "optimize",
            "step-by-step", "step by step", "multiple steps", "reason through",
            "prove that", "derive", "analyze", "analyse", "evaluate", "investigate",
            "why does", "why is", "how should i", "how would you design", "long answer",
            "essay", "report", "technical", "strategy", "pros and cons",
        )
        return any(term in text for term in complex_terms)
    def _local_first(self, prompt: str) -> bool:
        text = prompt.casefold()
        mode = self._routing_mode()
        if mode in {"cloud-first", "local-only"}:
            return mode == "local-only"
        if self._is_complex_prompt(prompt):
            return False
        simple_terms = ("classify", "categorize", "categorise", "extract", "parse", "json", "which window", "active window", "is this", "remember", "what do you remember")
        return mode == "local-first" or (mode == "balanced" and any(term in text for term in simple_terms))

    def _put_on_cooldown(self, key: str, error: str) -> None:
        state = self.states[key]
        retry = self._retry_after(error) or self.cooldown_default
        state.cooldown_until = time.time() + min(max(retry, 15), 3600)
        state.last_error = error
        state.last_status = "quota"
        state.failures += 1

    def _record_failure(self, key: str, error: str) -> None:
        state = self.states[key]
        state.failures += 1
        state.last_error = error
        state.last_status = "error"
        if state.failures >= 3:
            state.cooldown_until = time.time() + min(self.cooldown_default * state.failures, 300)

    def _success(self, key: str) -> None:
        state = self.states[key]
        state.successes += 1
        state.failures = 0
        state.cooldown_until = 0
        state.last_error = ""
        state.last_status = "available"

    @staticmethod
    def _is_quota_error(error: str) -> bool:
        text = error.casefold()
        return "429" in text or "quota" in text or "resource_exhausted" in text or "rate limit" in text or "rate_limit" in text

    @staticmethod
    def _retry_after(error: str) -> int | None:
        match = re.search(r"retry in\s+(\d+(?:\.\d+)?)s", error, re.IGNORECASE)
        return max(1, int(float(match.group(1)))) if match else None

    @staticmethod
    def _human_provider_message(key: str) -> str:
        return "Cloud AI is active." if key == "cloud" else "Local AI is active."
