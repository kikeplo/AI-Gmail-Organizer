"""Optional local AI engine for lightweight offline tasks."""

from __future__ import annotations

import base64
import io
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

    def status(self) -> dict[str, object]:
        if not self.enabled:
            return {"enabled": False, "available": False, "models": [], "model": self.model, "reason": "Local AI is disabled."}
        try:
            models = self.list_models()
            selected = self.model if self.model in models else (models[0] if models else "")
            return {"enabled": True, "available": bool(models), "models": models, "model": selected, "reason": "Local AI is ready." if models else "No local models installed."}
        except Exception as exc:
            return {"enabled": True, "available": False, "models": [], "model": self.model, "reason": str(exc)}

    def available(self) -> bool:
        return bool(self.status()["available"])

    def list_models(self) -> list[str]:
        data = self._request("GET", f"{self.base_url}/models")
        models = [str(item["id"]) for item in data.get("data", []) if isinstance(item, dict) and item.get("id")]
        if not models:
            raise LocalAIError("No local AI models were found. Install a model in your local AI runtime first.")
        return models

    def resolve_model(self) -> str:
        models = self.list_models()
        if self.model and self.model in models:
            return self.model
        blocked = ("embedding", "moderation", "image", "audio", "tts", "whisper")
        for model in models:
            if not any(token in model.lower() for token in blocked):
                return model
        return models[0]

    def chat(self, prompt: str, system: str = "") -> str:
        if not self.enabled:
            raise LocalAIError("Local AI is disabled.")
        body = {"model": self.resolve_model(), "messages": [{"role": "system", "content": system or "You are a concise local assistant for lightweight desktop tasks."}, {"role": "user", "content": prompt}]}
        data = self._request("POST", f"{self.base_url}/chat/completions", body)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LocalAIError("The local AI runtime returned an unsupported response format.") from exc
        if isinstance(content, list): content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return str(content).strip()

    def vision_json(self, prompt: str, image) -> dict:
        """Use a local multimodal model through an OpenAI-compatible vision request."""
        if not self.enabled:
            raise LocalAIError("Local AI is disabled.")
        encoded = base64.b64encode(self._image_bytes(image)).decode("ascii")
        body = {"model": self.resolve_model(), "messages": [{"role": "system", "content": "Return only valid JSON."}, {"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}}]}]}
        data = self._request("POST", f"{self.base_url}/chat/completions", body)
        try: raw = str(data["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc: raise LocalAIError("The local vision model returned an unsupported response.") from exc
        raw = raw.replace("```json", "").replace("```", "").strip()
        try: result = json.loads(raw)
        except json.JSONDecodeError as exc: raise LocalAIError("The local vision model did not return valid JSON.") from exc
        if not isinstance(result, dict): raise LocalAIError("The local vision model returned an invalid action format.")
        return result

    @staticmethod
    def _image_bytes(image) -> bytes:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def _request(self, method: str, url: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Accept": "application/json"}
        if body is not None: headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=45 if body is not None else 8) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LocalAIError(f"Local AI HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise LocalAIError(f"Local AI connection error: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise LocalAIError("The local AI runtime returned invalid JSON.") from exc
