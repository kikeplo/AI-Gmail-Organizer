"""Provider-agnostic AI gateway with text and vision support."""

from __future__ import annotations

import base64
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class AIProviderError(RuntimeError):
    pass


class AIProvider:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.base_url = os.getenv("OPENAI_BASE_URL", "").strip()
        self.provider = os.getenv("AI_PROVIDER", "").strip()
        self.model = os.getenv("OPENAI_MODEL", "").strip()

    @property
    def configured(self) -> bool:
        return bool(self.api_key or self.base_url)

    def _protocol(self) -> str:
        text = f"{self.provider} {self.base_url}".lower()
        if "generativelanguage.googleapis.com" in text or "gemini" in text:
            return "gemini"
        if "api.anthropic.com" in text or "anthropic" in text:
            return "anthropic"
        if "ollama" in text:
            return "openai_compatible"
        return "openai_compatible"

    def _base(self) -> str:
        base = self.base_url.rstrip("/")
        protocol = self._protocol()
        if base.endswith("/chat/completions"):
            base = base[: -len("/chat/completions")].rstrip("/")
        if protocol == "gemini":
            if not base:
                base = "https://generativelanguage.googleapis.com/v1beta/openai"
            elif "/openai" not in base:
                if base.endswith("/v1beta") or base.endswith("/v1"):
                    base += "/openai"
                else:
                    base += "/v1beta/openai"
            return base.rstrip("/")
        if protocol == "anthropic":
            return (base or "https://api.anthropic.com/v1").rstrip("/")
        if not base and "ollama" in self.provider.lower():
            return "http://localhost:11434/v1"
        return (base or "https://api.openai.com/v1").rstrip("/")

    def _headers(self, json_body: bool = False) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if json_body:
            headers["Content-Type"] = "application/json"
        if self.api_key:
            if self._protocol() == "anthropic":
                headers["x-api-key"] = self.api_key
                headers["anthropic-version"] = "2023-06-01"
            else:
                headers["Authorization"] = f"Bearer {self.api_key}"
        if self._protocol() == "gemini":
            headers["x-goog-api-client"] = "ai-gmail-organizer/1.4"
        return headers

    def _request(self, method: str, url: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(url, data=data, headers=self._headers(body is not None), method=method)
        try:
            with urlopen(request, timeout=90) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise AIProviderError(f"HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise AIProviderError(f"Connection error: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise AIProviderError("The AI provider returned invalid JSON.") from exc

    def list_models(self) -> list[str]:
        data = self._request("GET", f"{self._base()}/models")
        models = data.get("data", [])
        result = []
        for item in models:
            model_id = item.get("id") if isinstance(item, dict) else None
            if model_id:
                result.append(str(model_id))
        if not result:
            raise AIProviderError("The provider returned no models. This provider may not expose /models; its model must be supplied by the provider or a supported adapter.")
        return result

    def resolve_model(self) -> str:
        if self.model:
            return self.model
        models = self.list_models()
        blocked = ("embedding", "moderation", "image", "audio", "tts", "whisper")
        for model in models:
            if not any(token in model.lower() for token in blocked):
                return model
        return models[0]

    def chat(self, user_text: str, system_text: str = "") -> str:
        model = self.resolve_model()
        protocol = self._protocol()
        if protocol == "anthropic":
            body = {"model": model, "max_tokens": 2048, "system": system_text or "You are a helpful desktop assistant.", "messages": [{"role": "user", "content": user_text}]}
            data = self._request("POST", f"{self._base()}/messages", body)
            content = data.get("content", [])
            return "".join(item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text").strip()
        body = {"model": model, "messages": [{"role": "system", "content": system_text or "You are a helpful desktop assistant."}, {"role": "user", "content": user_text}]}
        data = self._request("POST", f"{self._base()}/chat/completions", body)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError("The provider returned a response in an unsupported format.") from exc
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return str(content).strip()

    def chat_with_image(self, user_text: str, image_base64: str, system_text: str = "") -> str:
        """Send a screenshot to a vision-capable model using a common multimodal format."""
        model = self.resolve_model()
        if self._protocol() == "anthropic":
            body = {
                "model": model,
                "max_tokens": 2048,
                "system": system_text or "You are a careful visual desktop assistant.",
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_base64}},
                ]}],
            }
            data = self._request("POST", f"{self._base()}/messages", body)
            content = data.get("content", [])
            return "".join(item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text").strip()
        image_url = f"data:image/png;base64,{image_base64}"
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system_text or "You are a careful visual desktop assistant."}, {"role": "user", "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": image_url}},
            ]}],
        }
        data = self._request("POST", f"{self._base()}/chat/completions", body)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError("The vision provider returned a response in an unsupported format.") from exc
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return str(content).strip()

    def classify_json(self, payload: list[dict], system_text: str) -> list[dict]:
        result = self.chat(json.dumps(payload), system_text)
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise AIProviderError("The AI provider did not return valid JSON for email classification.") from exc
        if not isinstance(parsed, list):
            raise AIProviderError("The AI provider returned an unexpected classification format.")
        return parsed
