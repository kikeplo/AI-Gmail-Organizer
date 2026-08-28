"""Optional local AI engine for lightweight offline tasks.

Uses a local Ollama-compatible HTTP endpoint when available. The engine is
intentionally independent from the cloud provider so the app can use local AI
for cheap/simple tasks and fall back to the configured cloud provider.
"""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LocalAIError(RuntimeError):
    pass


class LocalAIEngine:
    def __init__(self) -> None:
        self.base_url = os.getenv("LOCAL_AI_BASE_URL", "http://localhost:11434/v1").strip().rstrip("/")
        self.model = os.getenv("LOCAL_AI_MODEL", "").strip()
        self.enabled = os.getenv("LOCAL_AI_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}

    def available(self) -> bool:
        if not self.enabled:
            return False
        try:
            self._request("GET", f"{self.base_url}/models")
            return True
        except Exception:
            return False

    def list_models(self) -> list[str]:
        data = self._request("GET", f"{self.base_url}/models")
        models = []
        for item in data.get("data", []):
            if isinstance(item, dict) and item.get("id"):
                models.append(str(item["id"]))
        if not models:
            raise LocalAIError("No local AI models were found. Install/download a model in your local AI runtime first.")
        return models

    def resolve_model(self) -> str:
        if self.model:
            return self.model
        models = self.list_models()
        blocked = ("embedding", "moderation", "image", "audio")
        for model in models:
            if not any(token in model.lower() for token in blocked):
                return model
        return models[0]

    def chat(self, prompt: str, system: str = "") -> str:
        if not self.enabled:
            raise LocalAIError("Local AI is disabled.")
        body = {
            "model": self.resolve_model(),
            "messages": [
                {"role": "system", "content": system or "You are a concise local assistant for lightweight desktop tasks."},
                {"role": "user", "content": prompt},
            ],
        }
        data = self._request("POST", f"{self.base_url}/chat/completions", body)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LocalAIError("The local AI runtime returned an unsupported response format.") from exc
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return str(content).strip()

    def _request(self, method: str, url: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=8) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LocalAIError(f"Local AI HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise LocalAIError(f"Local AI connection error: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise LocalAIError("The local AI runtime returned invalid JSON.") from exc
