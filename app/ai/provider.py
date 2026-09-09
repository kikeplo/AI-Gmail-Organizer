"""Provider-agnostic AI gateway with text, vision, and capability detection."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class AIProviderError(RuntimeError):
    pass


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

    @property
    def configured(self) -> bool:
        return bool(self.api_key or self.base_url)

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

    def _headers(self, json_body: bool = False) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if json_body: headers["Content-Type"] = "application/json"
        if self.api_key:
            if self._protocol() == "anthropic":
                headers["x-api-key"] = self.api_key; headers["anthropic-version"] = "2023-06-01"
            else: headers["Authorization"] = f"Bearer {self.api_key}"
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
        except URLError as exc: raise AIProviderError(f"Connection error: {exc.reason}") from exc
        except json.JSONDecodeError as exc: raise AIProviderError("The AI provider returned invalid JSON.") from exc

    def list_models(self) -> list[str]:
        data = self._request("GET", f"{self._base()}/models")
        result = [str(item.get("id")) for item in data.get("data", []) if isinstance(item, dict) and item.get("id")]
        if not result: raise AIProviderError("The provider returned no models. This provider may not expose /models.")
        return result

    def resolve_model(self) -> str:
        if self._resolved_model:
            return self._resolved_model
        models = self.list_models()
        blocked = ("embedding", "moderation", "image", "audio", "tts", "whisper")
        preferred = [m for m in models if not any(token in m.lower() for token in blocked)]
        self._resolved_model = preferred[0] if preferred else models[0]
        return self._resolved_model

    def capabilities(self, model: str | None = None) -> AICapabilities:
        """Infer useful capabilities from provider/model metadata without requiring a paid probe."""
        selected = (model or self.model or self._resolved_model or "").lower()
        protocol = self._protocol()
        vision = any(token in selected for token in ("vision", "-vl", "vlm", "gemini", "claude-3", "claude-4", "gpt-4o", "gpt-4.1", "gpt-5", "qwen2.5-vl", "qwen3-vl", "llama-4"))
        structured = protocol in {"gemini", "anthropic", "openai_compatible"}
        tool_calling = any(token in selected for token in ("gpt-4", "gpt-5", "gemini", "claude", "qwen", "llama-4", "mistral"))
        if "vision" in selected or "vl" in selected: vision = True
        return AICapabilities(text=True, vision=vision, structured_output=structured, tool_calling=tool_calling, model_listing=True)

    def chat(self, user_text: str, system_text: str = "") -> str:
        model = self.resolve_model()
        if self._protocol() == "anthropic":
            body = {"model": model, "max_tokens": 2048, "system": system_text or "You are a helpful desktop assistant.", "messages": [{"role": "user", "content": user_text}]}
            data = self._request("POST", f"{self._base()}/messages", body)
            return "".join(item.get("text", "") for item in data.get("content", []) if isinstance(item, dict) and item.get("type") == "text").strip()
        body = {"model": model, "messages": [{"role": "system", "content": system_text or "You are a helpful desktop assistant."}, {"role": "user", "content": user_text}]}
        data = self._request("POST", f"{self._base()}/chat/completions", body)
        try: content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc: raise AIProviderError("The provider returned a response in an unsupported format.") from exc
        if isinstance(content, list): content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return str(content).strip()

    def vision_json(self, prompt: str, image_base64: str) -> dict:
        model = self.resolve_model()
        if not self.capabilities(model).vision:
            raise AIProviderError("The selected AI model does not appear to support vision. Choose a vision-capable model or configure a local vision provider.")
        if self._protocol() == "anthropic":
            body = {"model": model, "max_tokens": 700, "system": "Return only valid JSON.", "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_base64}}]}]}
            data = self._request("POST", f"{self._base()}/messages", body)
            raw = "".join(item.get("text", "") for item in data.get("content", []) if isinstance(item, dict) and item.get("type") == "text").strip()
        else:
            body = {"model": model, "messages": [{"role": "system", "content": "Return only valid JSON."}, {"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}]}]}
            data = self._request("POST", f"{self._base()}/chat/completions", body)
            try: raw = str(data["choices"][0]["message"]["content"]).strip()
            except (KeyError, IndexError, TypeError) as exc: raise AIProviderError("The vision provider returned an unsupported response.") from exc
        raw = raw.replace("```json", "").replace("```", "").strip()
        try: result = json.loads(raw)
        except json.JSONDecodeError as exc: raise AIProviderError("The vision model did not return valid JSON.") from exc
        if not isinstance(result, dict): raise AIProviderError("The vision model returned an invalid action format.")
        return result

    def classify_json(self, payload: list[dict], system_text: str) -> list[dict]:
        result = self.chat(json.dumps(payload), system_text)
        cleaned = result.replace("```json", "").replace("```", "").strip()
        try: parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc: raise AIProviderError("The AI provider did not return valid JSON for email classification.") from exc
        if not isinstance(parsed, list): raise AIProviderError("The AI provider returned an unexpected classification format.")
        return parsed
