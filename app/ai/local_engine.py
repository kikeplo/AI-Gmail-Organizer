"""Optional local AI engine for lightweight offline tasks."""

from __future__ import annotations

import base64
import io
import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LocalAIError(RuntimeError):
    pass


class LocalAIEngine:
    """Local AI client with first-class Ollama support and OpenAI-compatible fallback."""

    DEFAULT_BASE_URL = "http://localhost:11434/v1"
    DEFAULT_MODEL = "qwen3:1.7b"
    FAST_MODEL = "qwen3:1.7b"
    QUALITY_MODEL = "qwen3:4b"
    DEFAULT_KEEP_ALIVE = "30m"
    DEFAULT_NUM_CTX = 4096

    def __init__(self) -> None:
        self.base_url = os.getenv("LOCAL_AI_BASE_URL", self.DEFAULT_BASE_URL).strip().rstrip("/") or self.DEFAULT_BASE_URL
        self.model = os.getenv("LOCAL_AI_MODEL", self.DEFAULT_MODEL).strip() or self.DEFAULT_MODEL
        self.enabled = os.getenv("LOCAL_AI_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}

    @property
    def ollama_executable(self) -> str | None:
        found = shutil.which("ollama")
        if found:
            return found
        local_appdata = os.getenv("LOCALAPPDATA", "")
        candidates = [
            Path(local_appdata) / "Programs" / "Ollama" / "ollama.exe" if local_appdata else None,
            Path(local_appdata) / "Ollama" / "ollama.exe" if local_appdata else None,
            Path(os.getenv("PROGRAMFILES", "C:\\Program Files")) / "Ollama" / "ollama.exe",
            Path(os.getenv("PROGRAMFILES(X86)", "C:\\Program Files (x86)")) / "Ollama" / "ollama.exe",
        ]
        for path in candidates:
            if path is not None and path.is_file():
                return str(path)
        return None

    @property
    def is_ollama_endpoint(self) -> bool:
        return ":11434" in self.base_url.lower() or "ollama" in self.base_url.lower()

    @property
    def ollama_base_url(self) -> str:
        """Derive Ollama's native API root from an OpenAI-compatible base URL."""
        base = self.base_url.rstrip("/")
        if base.lower().endswith("/v1"):
            base = base[:-3].rstrip("/")
        return base or "http://localhost:11434"

    def status(self) -> dict[str, object]:
        if not self.enabled:
            return {"enabled": False, "available": False, "ollama_installed": bool(self.ollama_executable), "models": [], "model": self.model, "reason": "Local AI is disabled."}
        try:
            models = self.list_models()
            selected = self.model if self.model in models else (models[0] if models else "")
            return {"enabled": True, "available": bool(models), "ollama_installed": bool(self.ollama_executable), "models": models, "model": selected, "reason": "Local AI is ready." if models else "No local models installed."}
        except Exception as exc:
            installed = bool(self.ollama_executable)
            return {"enabled": True, "available": False, "ollama_installed": installed, "models": [], "model": self.model, "reason": str(exc) if installed or not self.is_ollama_endpoint else "Ollama is not installed or not running."}

    def available(self) -> bool:
        return bool(self.status()["available"])

    def list_models(self) -> list[str]:
        if self.is_ollama_endpoint:
            data = self._request("GET", f"{self.ollama_base_url}/api/tags")
            models = [str(item["name"]) for item in data.get("models", []) if isinstance(item, dict) and item.get("name")]
        else:
            data = self._request("GET", f"{self.base_url}/models")
            models = [str(item["id"]) for item in data.get("data", []) if isinstance(item, dict) and item.get("id")]
        if not models:
            raise LocalAIError("No local AI models were found. Install a model in your local AI runtime first.")
        return models

    def resolve_model(self) -> str:
        models = self.list_models()
        if self.model and self.model in models:
            return self.model
        for preferred in (self.FAST_MODEL, self.QUALITY_MODEL):
            if preferred in models:
                return preferred
        blocked = ("embedding", "moderation", "image", "audio", "tts", "whisper")
        for model in models:
            if not any(token in model.lower() for token in blocked):
                return model
        return models[0]

    def _thinking_enabled(self) -> bool:
        return os.getenv("LOCAL_AI_THINKING", "0").strip().lower() in {"1", "true", "yes", "on"}

    def _keep_alive(self) -> str | int:
        value = os.getenv("LOCAL_AI_KEEP_ALIVE", self.DEFAULT_KEEP_ALIVE).strip()
        if value.lower() in {"0", "0s", "false", "off"}:
            return 0
        return value or self.DEFAULT_KEEP_ALIVE

    def _num_ctx(self) -> int:
        try:
            return max(1024, min(int(os.getenv("LOCAL_AI_NUM_CTX", str(self.DEFAULT_NUM_CTX))), 32768))
        except (TypeError, ValueError):
            return self.DEFAULT_NUM_CTX

    def _max_tokens(self) -> int:
        try:
            return max(32, min(int(os.getenv("LOCAL_AI_MAX_TOKENS", "192")), 1024))
        except (TypeError, ValueError):
            return 192

    def _request_options(self) -> dict[str, object]:
        """Return Ollama generation controls tuned for responsive desktop use."""
        if not self.is_ollama_endpoint:
            return {}
        return {"num_ctx": self._num_ctx(), "temperature": 0.2, "num_predict": self._max_tokens()}

    def chat(self, prompt: str, system: str = "") -> str:
        if not self.enabled:
            raise LocalAIError("Local AI is disabled.")
        model = self.resolve_model()
        messages = [
            {"role": "system", "content": system or "You are a concise local assistant for lightweight desktop tasks."},
            {"role": "user", "content": prompt},
        ]
        if self.is_ollama_endpoint:
            body = {"model": model, "messages": messages, "stream": False, "think": self._thinking_enabled(), "keep_alive": self._keep_alive(), "options": self._request_options()}
            data = self._request("POST", f"{self.ollama_base_url}/api/chat", body)
            try:
                message = data["message"]
                content = message.get("content", "")
            except (KeyError, TypeError) as exc:
                raise LocalAIError("The local AI runtime returned an unsupported response format.") from exc
        else:
            body = {"model": model, "messages": messages, "stream": False}
            data = self._request("POST", f"{self.base_url}/chat/completions", body)
            try:
                message = data["choices"][0]["message"]
                content = message.get("content", "")
            except (KeyError, IndexError, TypeError) as exc:
                raise LocalAIError("The local AI runtime returned an unsupported response format.") from exc
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return str(content).strip()

    def vision_json(self, prompt: str, image) -> dict:
        """Use a local multimodal model through native Ollama or OpenAI-compatible vision."""
        if not self.enabled:
            raise LocalAIError("Local AI is disabled.")
        encoded = base64.b64encode(self._image_bytes(image)).decode("ascii")
        if self.is_ollama_endpoint:
            body = {"model": self.resolve_model(), "messages": [{"role": "system", "content": "Return only valid JSON."}, {"role": "user", "content": prompt, "images": [encoded]}], "stream": False, "think": self._thinking_enabled(), "keep_alive": self._keep_alive(), "options": self._request_options()}
            data = self._request("POST", f"{self.ollama_base_url}/api/chat", body)
            try:
                raw = str(data["message"]["content"]).strip()
            except (KeyError, TypeError) as exc:
                raise LocalAIError("The local vision model returned an unsupported response.") from exc
        else:
            body = {"model": self.resolve_model(), "messages": [{"role": "system", "content": "Return only valid JSON."}, {"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}}]}], "stream": False}
            data = self._request("POST", f"{self.base_url}/chat/completions", body)
            try:
                raw = str(data["choices"][0]["message"]["content"]).strip()
            except (KeyError, IndexError, TypeError) as exc:
                raise LocalAIError("The local vision model returned an unsupported response.") from exc
        raw = raw.replace("```json", "").replace("```", "").strip()
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LocalAIError("The local vision model did not return valid JSON.") from exc
        if not isinstance(result, dict):
            raise LocalAIError("The local vision model returned an invalid action format.")
        return result

    def install_model(self, model: str | None = None) -> str:
        model_name = (model or self.model or self.DEFAULT_MODEL).strip()
        if not model_name:
            raise LocalAIError("Enter a local model name first.")
        executable = self.ollama_executable
        if not executable:
            raise LocalAIError("Ollama is not installed. Install Ollama, then use this button again.")
        try:
            completed = subprocess.run([executable, "pull", model_name], check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
        except OSError as exc:
            raise LocalAIError(f"Could not start Ollama: {exc}") from exc
        output = (completed.stdout or completed.stderr or "").strip()
        if completed.returncode != 0:
            raise LocalAIError(f"Ollama could not install {model_name}.\n\n{output or 'Unknown Ollama error.'}")
        return output or f"Ollama installed {model_name}."

    @staticmethod
    def _image_bytes(image) -> bytes:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def _request(self, method: str, url: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=4 if body is None else 45) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LocalAIError(f"Local AI HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise LocalAIError(f"Local AI connection error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise LocalAIError(f"Local AI connection timeout: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise LocalAIError("The local AI runtime returned invalid JSON.") from exc
