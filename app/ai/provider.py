"""Provider-agnostic AI gateway with text, vision, and API-key failover."""

from __future__ import annotations

import json
import os
import random
import re
import threading
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class AIProviderError(RuntimeError):
    pass


class AICancelled(AIProviderError):
    """Raised when the user explicitly stops an active AI request."""


@dataclass(frozen=True)
class AICapabilities:
    text: bool = True
    vision: bool = False
    structured_output: bool = False
    tool_calling: bool = False
    model_listing: bool = False

    def labels(self) -> list[str]:
        labels = ["Text"] if self.text else []
        if self.vision: labels.append("Vision")
        if self.structured_output: labels.append("Structured output")
        if self.tool_calling: labels.append("Tool use")
        if self.model_listing: labels.append("Model list")
        return labels


class AIProvider:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.base_url = os.getenv("OPENAI_BASE_URL", "").strip()
        self.provider = os.getenv("AI_PROVIDER", "").strip()
        self.model = os.getenv("OPENAI_MODEL", "").strip()
        self._resolved_model: str | None = self.model or None
        self.fallback_models = [item.strip() for item in os.getenv("AI_FALLBACK_MODELS", "").split(",") if item.strip()]
        self.retry_attempts = max(0, min(int(os.getenv("AI_TRANSIENT_RETRIES", "1")), 3))
        self.retry_base_seconds = max(0.2, float(os.getenv("AI_RETRY_BASE_SECONDS", "0.8")))

        # API-key failover. OPENAI_API_KEY remains the primary/legacy setting.
        # Additional keys can be supplied as a comma-separated list or using
        # OPENAI_API_KEY_BACKUP, OPENAI_API_KEY_BACKUP_2, ...
        configured_keys: list[str] = []
        for value in (
            self.api_key,
            *os.getenv("OPENAI_API_KEYS", "").split(","),
            os.getenv("OPENAI_API_KEY_BACKUP", ""),
        ):
            key = value.strip()
            if key and key not in configured_keys:
                configured_keys.append(key)
        for index in range(2, 11):
            key = os.getenv(f"OPENAI_API_KEY_BACKUP_{index}", "").strip()
            if key and key not in configured_keys:
                configured_keys.append(key)
        self.api_keys = configured_keys
        self._key_cooldowns: dict[str, float] = {key: 0.0 for key in self.api_keys}
        self._active_key_index = 0
        self._cancel_event = threading.Event()
        self._active_response = None
        self._active_lock = threading.Lock()

    def begin_operation(self) -> None:
        with self._active_lock:
            self._cancel_event.clear()

    def cancel(self) -> None:
        self._cancel_event.set()
        with self._active_lock:
            response = self._active_response
        if response is not None:
            try:
                response.close()
            except Exception:
                pass

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def _check_cancelled(self) -> None:
        if self._cancel_event.is_set():
            raise AICancelled("AI request stopped by user.")

    @property
    def configured(self) -> bool:
        return bool(self.api_keys or self.base_url)

    def _protocol(self) -> str:
        text = f"{self.provider} {self.base_url}".lower()
        if "generativelanguage.googleapis.com" in text or "gemini" in text: return "gemini"
        if "api.anthropic.com" in text or "anthropic" in text: return "anthropic"
        return "openai_compatible"

    def _base(self) -> str:
        base = self.base_url.rstrip("/")
        protocol = self._protocol()
        if base.endswith("/chat/completions"):
            base = base[: -len("/chat/completions")].rstrip("/")
        if protocol == "gemini":
            if not base: base = "https://generativelanguage.googleapis.com/v1beta/openai"
            elif "/openai" not in base: base += "/openai" if base.endswith(("/v1", "/v1beta")) else "/v1beta/openai"
            return base.rstrip("/")
        if protocol == "anthropic": return (base or "https://api.anthropic.com/v1").rstrip("/")
        if not base and "ollama" in self.provider.lower(): return "http://localhost:11434/v1"
        return (base or "https://api.openai.com/v1").rstrip("/")

    def _headers(self, json_body: bool = False, api_key: str | None = None) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if json_body: headers["Content-Type"] = "application/json"
        key = api_key if api_key is not None else self.api_key
        if key:
            if self._protocol() == "anthropic":
                headers["x-api-key"] = key
                headers["anthropic-version"] = "2023-06-01"
            else:
                headers["Authorization"] = f"Bearer {key}"
        return headers

    def _request(self, method: str, url: str, body: dict | None = None, api_key: str | None = None) -> dict:
        self._check_cancelled()
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(url, data=data, headers=self._headers(body is not None, api_key), method=method)
        response = None
        try:
            response = urlopen(request, timeout=90)
            with self._active_lock:
                self._active_response = response
            self._check_cancelled()
            raw = response.read().decode("utf-8")
            self._check_cancelled()
            return json.loads(raw) if raw else {}
        except AICancelled:
            raise
        except HTTPError as exc:
            if self._cancel_event.is_set():
                raise AICancelled("AI request stopped by user.") from exc
            detail = exc.read().decode("utf-8", errors="replace")
            raise AIProviderError(f"HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            if self._cancel_event.is_set():
                raise AICancelled("AI request stopped by user.") from exc
            raise AIProviderError(f"Connection error: {exc.reason}") from exc
        except TimeoutError as exc:
            if self._cancel_event.is_set():
                raise AICancelled("AI request stopped by user.") from exc
            raise AIProviderError(f"Connection timeout: {exc}") from exc
        except (OSError, ValueError) as exc:
            if self._cancel_event.is_set():
                raise AICancelled("AI request stopped by user.") from exc
            raise AIProviderError(f"AI connection failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise AIProviderError("The AI provider returned invalid JSON.") from exc
        finally:
            with self._active_lock:
                if response is self._active_response:
                    self._active_response = None
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass

    @staticmethod
    def _error_code(error: str) -> int | None:
        match = re.search(r"HTTP\s+(\d{3})", error, re.IGNORECASE)
        return int(match.group(1)) if match else None

    @staticmethod
    def _is_transient_error(error: str) -> bool:
        text = error.casefold()
        return any(marker in text for marker in ("http 408:", "http 429:", "http 500:", "http 502:", "http 503:", "http 504:"))

    @staticmethod
    def _is_key_failover_error(error: str) -> bool:
        code = AIProvider._error_code(error)
        text = error.casefold()
        return code in {401, 403, 408, 429, 500, 502, 503, 504} or "quota" in text or "resource_exhausted" in text or "rate limit" in text

    def _sleep_before_retry(self, attempt: int) -> None:
        delay = min(self.retry_base_seconds * (2 ** attempt) + random.uniform(0.0, 0.25), 5.0)
        if self._cancel_event.wait(delay):
            raise AICancelled("AI request stopped by user.")

    def _available_keys(self) -> list[str]:
        if not self.api_keys:
            return [""]
        now = time.time()
        ordered = self.api_keys[self._active_key_index:] + self.api_keys[:self._active_key_index]
        return [key for key in ordered if now >= self._key_cooldowns.get(key, 0.0)]

    def _mark_key_failed(self, key: str, error: str) -> None:
        if not key:
            return
        code = self._error_code(error)
        if code == 401:
            cooldown = 3600
        elif code in {429} or "quota" in error.casefold() or "resource_exhausted" in error.casefold():
            cooldown = 300
        elif code in {500, 502, 503, 504}:
            cooldown = 20
        elif code == 403:
            cooldown = 300
        else:
            cooldown = 15
        self._key_cooldowns[key] = time.time() + cooldown
        try:
            self._active_key_index = (self.api_keys.index(key) + 1) % len(self.api_keys)
        except ValueError:
            pass

    def _mark_key_success(self, key: str) -> None:
        if not key or key not in self.api_keys:
            return
        self._key_cooldowns[key] = 0.0
        self._active_key_index = self.api_keys.index(key)

    def list_models(self) -> list[str]:
        last_error: str | None = None
        for key in self._available_keys():
            try:
                data = self._request("GET", f"{self._base()}/models", api_key=key or None)
                result = [str(item.get("id")) for item in data.get("data", []) if isinstance(item, dict) and item.get("id")]
                if not result:
                    raise AIProviderError("The provider returned no models. This provider may not expose /models.")
                self._mark_key_success(key)
                return result
            except AIProviderError as exc:
                last_error = str(exc)
                if self._is_key_failover_error(last_error):
                    self._mark_key_failed(key, last_error)
                else:
                    break
        raise AIProviderError(last_error or "The provider could not list available models.")

    def resolve_model(self) -> str:
        if self._resolved_model:
            return self._resolved_model
        models = self.list_models()
        blocked = ("embedding", "moderation", "image", "audio", "tts", "whisper")
        preferred = [m for m in models if not any(token in m.lower() for token in blocked)]
        self._resolved_model = preferred[0] if preferred else models[0]
        return self._resolved_model

    def _model_candidates(self, *, require_vision: bool = False) -> list[str]:
        primary = self.resolve_model()
        configured = [primary, *self.fallback_models]
        if self._protocol() == "gemini":
            configured.extend(["gemini-3.6-flash", "gemini-3.5-flash"])
        result: list[str] = []
        for model in configured:
            if model in result:
                continue
            if require_vision and not self.capabilities(model).vision:
                continue
            result.append(model)
        return result or [primary]

    def capabilities(self, model: str | None = None) -> AICapabilities:
        """Infer useful capabilities from provider/model metadata without requiring a paid probe."""
        selected = (model or self.model or self._resolved_model or "").lower()
        protocol = self._protocol()
        vision = any(token in selected for token in ("vision", "-vl", "vlm", "gemini", "claude-3", "claude-4", "gpt-4o", "gpt-4.1", "gpt-5", "qwen2.5-vl", "qwen3-vl", "llama-4"))
        structured = protocol in {"gemini", "anthropic", "openai_compatible"}
        tool_calling = any(token in selected for token in ("gpt-4", "gpt-5", "gemini", "claude", "qwen", "llama-4", "mistral"))
        if "vision" in selected or "vl" in selected: vision = True
        return AICapabilities(text=True, vision=vision, structured_output=structured, tool_calling=tool_calling, model_listing=True)

    def _chat_once(self, model: str, user_text: str, system_text: str, api_key: str | None = None) -> str:
        if self._protocol() == "anthropic":
            body = {"model": model, "max_tokens": 2048, "system": system_text or "You are a helpful desktop assistant.", "messages": [{"role": "user", "content": user_text}]}
            data = self._request("POST", f"{self._base()}/messages", body, api_key=api_key)
            return "".join(item.get("text", "") for item in data.get("content", []) if isinstance(item, dict) and item.get("type") == "text").strip()
        body = {"model": model, "messages": [{"role": "system", "content": system_text or "You are a helpful desktop assistant."}, {"role": "user", "content": user_text}]}
        data = self._request("POST", f"{self._base()}/chat/completions", body, api_key=api_key)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError("The provider returned a response in an unsupported format.") from exc
        if isinstance(content, list): content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return str(content).strip()

    def chat(self, user_text: str, system_text: str = "") -> str:
        self._check_cancelled()
        last_error: str | None = None
        for model in self._model_candidates():
            for key in self._available_keys():
                for attempt in range(self.retry_attempts + 1):
                    try:
                        result = self._chat_once(model, user_text, system_text, api_key=key or None)
                        self._mark_key_success(key)
                        self._resolved_model = model
                        return result
                    except AIProviderError as exc:
                        last_error = str(exc)
                        if self._is_key_failover_error(last_error):
                            self._mark_key_failed(key, last_error)
                        if not self._is_transient_error(last_error) or attempt >= self.retry_attempts:
                            break
                        self._sleep_before_retry(attempt)
                    
        raise AIProviderError(self._friendly_transient_error(last_error))

    def _vision_once(self, model: str, prompt: str, image_base64: str, api_key: str | None = None) -> dict:
        if not self.capabilities(model).vision:
            raise AIProviderError("The selected AI model does not appear to support vision.")
        if self._protocol() == "anthropic":
            body = {"model": model, "max_tokens": 700, "system": "Return only valid JSON.", "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_base64}}]}]}
            data = self._request("POST", f"{self._base()}/messages", body, api_key=api_key)
            raw = "".join(item.get("text", "") for item in data.get("content", []) if isinstance(item, dict) and item.get("type") == "text").strip()
        else:
            body = {"model": model, "messages": [{"role": "system", "content": "Return only valid JSON."}, {"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}]}]}
            data = self._request("POST", f"{self._base()}/chat/completions", body, api_key=api_key)
            try:
                raw = str(data["choices"][0]["message"]["content"]).strip()
            except (KeyError, IndexError, TypeError) as exc:
                raise AIProviderError("The vision provider returned an unsupported response.") from exc
        raw = raw.replace("```json", "").replace("```", "").strip()
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AIProviderError("The vision model did not return valid JSON.") from exc
        if not isinstance(result, dict):
            raise AIProviderError("The vision model returned an invalid action format.")
        return result

    def vision_json(self, prompt: str, image_base64: str) -> dict:
        self._check_cancelled()
        last_error: str | None = None
        for model in self._model_candidates(require_vision=True):
            for key in self._available_keys():
                for attempt in range(self.retry_attempts + 1):
                    try:
                        result = self._vision_once(model, prompt, image_base64, api_key=key or None)
                        self._mark_key_success(key)
                        self._resolved_model = model
                        return result
                    except AIProviderError as exc:
                        last_error = str(exc)
                        if self._is_key_failover_error(last_error):
                            self._mark_key_failed(key, last_error)
                        if not self._is_transient_error(last_error) or attempt >= self.retry_attempts:
                            break
                        self._sleep_before_retry(attempt)
        raise AIProviderError(self._friendly_transient_error(last_error))

    def classify_json(self, payload: list[dict], system_text: str) -> list[dict]:
        result = self.chat(json.dumps(payload), system_text)
        cleaned = result.replace("```json", "").replace("```", "").strip()
        try: parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc: raise AIProviderError("The AI provider did not return valid JSON for email classification.") from exc
        if not isinstance(parsed, list): raise AIProviderError("The AI provider returned an unexpected classification format.")
        return parsed

    @staticmethod
    def _friendly_transient_error(error: str | None) -> str:
        if error and any(marker in error.casefold() for marker in ("http 503:", "http 500:", "http 502:", "http 504:", "http 429:", "http 408:")):
            return "The AI provider is temporarily overloaded or rate-limited. The request was retried across the available API key(s) and fallback model(s), but they were unavailable. Please try again in a moment.\n\n" + error
        return error or "The AI provider could not complete the request."
