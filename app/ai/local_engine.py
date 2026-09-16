"""Local Ollama AI engine optimized for fast desktop and Gmail tasks."""

from __future__ import annotations

import base64
import io
import json
import os
import shutil
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LocalAIError(RuntimeError):
    pass


class LocalAIEngine:
    """Small, fast Ollama client with separate text and vision paths."""

    DEFAULT_BASE_URL = "http://localhost:11434/v1"
    DEFAULT_MODEL = "qwen3:1.7b"
    FAST_MODEL = "qwen3:1.7b"
    QUALITY_MODEL = "qwen3:4b"
    VISION_MODEL = "qwen3-vl:2b"
    REQUIRED_OLLAMA_MODELS = (FAST_MODEL, QUALITY_MODEL, VISION_MODEL)
    DEFAULT_KEEP_ALIVE = "30m"
    DEFAULT_NUM_CTX = 2048
    DEFAULT_TEXT_PREDICT = 96
    DEFAULT_VISION_PREDICT = 48
    DEFAULT_VISION_MAX_EDGE = 960

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
        return next((str(path) for path in candidates if path and path.is_file()), None)

    @property
    def is_ollama_endpoint(self) -> bool:
        return ":11434" in self.base_url.lower() or "ollama" in self.base_url.lower()

    @property
    def ollama_base_url(self) -> str:
        base = self.base_url.rstrip("/")
        if base.lower().endswith("/v1"):
            base = base[:-3].rstrip("/")
        return base or "http://localhost:11434"

    def status(self) -> dict[str, object]:
        if not self.enabled:
            return {"enabled": False, "available": False, "ollama_installed": bool(self.ollama_executable), "models": [], "model": self.model, "missing_models": list(self.REQUIRED_OLLAMA_MODELS), "vision_model": "", "reason": "Local AI is disabled."}
        try:
            models = self.list_models()
            missing = [name for name in self.REQUIRED_OLLAMA_MODELS if name not in models] if self.is_ollama_endpoint else []
            return {"enabled": True, "available": bool(models), "ollama_installed": bool(self.ollama_executable), "models": models, "model": self.resolve_model_from(models), "missing_models": missing, "vision_model": self._find_installed_vision_model(models), "reason": "Local AI is ready." if not missing else f"Missing local models: {', '.join(missing)}"}
        except Exception as exc:
            return {"enabled": True, "available": False, "ollama_installed": bool(self.ollama_executable), "models": [], "model": self.model, "missing_models": list(self.REQUIRED_OLLAMA_MODELS) if self.is_ollama_endpoint else [], "vision_model": "", "reason": str(exc)}

    def available(self) -> bool:
        return bool(self.status()["available"])

    def list_models(self) -> list[str]:
        if self.is_ollama_endpoint:
            data = self._request("GET", f"{self.ollama_base_url}/api/tags", timeout_seconds=4)
            models = [str(item["name"]) for item in data.get("models", []) if isinstance(item, dict) and item.get("name")]
        else:
            data = self._request("GET", f"{self.base_url}/models", timeout_seconds=4)
            models = [str(item["id"]) for item in data.get("data", []) if isinstance(item, dict) and item.get("id")]
        if not models:
            raise LocalAIError("No local AI models were found. Install a model in Settings first.")
        return models

    @classmethod
    def _find_installed_vision_model(cls, models: list[str]) -> str:
        if cls.VISION_MODEL in models:
            return cls.VISION_MODEL
        for model in models:
            if model.startswith("qwen3-vl:"):
                return model
        return ""

    def resolve_model_from(self, models: list[str]) -> str:
        if self.model in models:
            return self.model
        for preferred in (self.FAST_MODEL, self.QUALITY_MODEL):
            if preferred in models:
                return preferred
        for model in models:
            lower = model.lower()
            if not any(token in lower for token in ("embedding", "moderation", "image", "audio", "tts", "whisper", "qwen3-vl")):
                return model
        raise LocalAIError("No suitable local text model is installed.")

    def resolve_model(self) -> str:
        return self.resolve_model_from(self.list_models())

    def resolve_vision_model(self) -> str:
        selected = self._find_installed_vision_model(self.list_models())
        if not selected:
            raise LocalAIError(f"No local vision model is installed. Install {self.VISION_MODEL} from Settings first.")
        return selected

    def _keep_alive(self) -> str | int:
        value = os.getenv("LOCAL_AI_KEEP_ALIVE", self.DEFAULT_KEEP_ALIVE).strip()
        if value.lower() in {"0", "0s", "false", "off"}:
            return 0
        return value or self.DEFAULT_KEEP_ALIVE

    @staticmethod
    def _thinking_enabled() -> bool:
        return os.getenv("LOCAL_AI_THINKING", "0").strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _int_env(name: str, default: int, minimum: int, maximum: int) -> int:
        try:
            return max(minimum, min(int(os.getenv(name, str(default))), maximum))
        except (TypeError, ValueError):
            return default

    def _text_predict(self) -> int:
        return self._int_env("LOCAL_AI_MAX_TOKENS", self.DEFAULT_TEXT_PREDICT, 32, 256)

    def _vision_predict(self) -> int:
        return self._int_env("LOCAL_AI_VISION_MAX_TOKENS", self.DEFAULT_VISION_PREDICT, 24, 128)

    def chat(self, prompt: str, system: str = "") -> str:
        if not self.enabled:
            raise LocalAIError("Local AI is disabled.")
        model = self.resolve_model()
        messages = [{"role": "system", "content": system or "You are a concise local assistant. Return only the useful answer."}, {"role": "user", "content": prompt}]
        if self.is_ollama_endpoint:
            body = {"model": model, "messages": messages, "stream": False, "think": self._thinking_enabled(), "keep_alive": self._keep_alive(), "options": {"num_ctx": self.DEFAULT_NUM_CTX, "temperature": 0.1, "num_predict": self._text_predict()}}
            data = self._request("POST", f"{self.ollama_base_url}/api/chat", body, timeout_seconds=30)
            try:
                content = data["message"].get("content", "")
            except (KeyError, TypeError) as exc:
                raise LocalAIError("The local AI runtime returned an unsupported response format.") from exc
        else:
            data = self._request("POST", f"{self.base_url}/chat/completions", {"model": model, "messages": messages, "stream": False}, timeout_seconds=30)
            try:
                content = data["choices"][0]["message"].get("content", "")
            except (KeyError, IndexError, TypeError) as exc:
                raise LocalAIError("The local AI runtime returned an unsupported response format.") from exc
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return str(content).strip()

    def vision_json(self, prompt: str, image) -> dict:
        if not self.enabled:
            raise LocalAIError("Local AI is disabled.")
        encoded = base64.b64encode(self._image_bytes(image)).decode("ascii")
        model = self.resolve_vision_model() if self.is_ollama_endpoint else self.resolve_model()
        if self.is_ollama_endpoint:
            body = {"model": model, "messages": [{"role": "system", "content": "Return ONLY valid JSON. No explanation. Never use markdown."}, {"role": "user", "content": prompt, "images": [encoded]}], "stream": False, "think": False, "keep_alive": self._keep_alive(), "options": {"num_ctx": 2048, "temperature": 0.0, "num_predict": self._vision_predict()}}
            data = self._request("POST", f"{self.ollama_base_url}/api/chat", body, timeout_seconds=120)
            try:
                raw = str(data["message"].get("content", "")).strip()
            except (KeyError, TypeError) as exc:
                raise LocalAIError("The local vision model returned an unsupported response.") from exc
        else:
            body = {"model": model, "messages": [{"role": "system", "content": "Return ONLY valid JSON."}, {"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}}]}], "stream": False}
            data = self._request("POST", f"{self.base_url}/chat/completions", body, timeout_seconds=120)
            try:
                raw = str(data["choices"][0]["message"].get("content", "")).strip()
            except (KeyError, IndexError, TypeError) as exc:
                raise LocalAIError("The local vision model returned an unsupported response format.") from exc
        raw = raw.replace("```json", "").replace("```", "").strip()
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LocalAIError("The local vision model did not return valid JSON.") from exc
        if not isinstance(result, dict):
            raise LocalAIError("The local vision model returned an invalid action format.")
        return result

    @staticmethod
    def _image_bytes(image, max_edge: int = 960) -> bytes:
        try:
            from PIL import Image
            prepared = image.copy()
            prepared.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        except Exception:
            prepared = image
        buffer = io.BytesIO()
        prepared.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()

    def _ensure_ollama_server(self, executable: str) -> None:
        try:
            self._request("GET", f"{self.ollama_base_url}/api/tags", timeout_seconds=1.5)
            return
        except LocalAIError:
            raise LocalAIError("Ollama is installed, but its local service is not running. Start Ollama, then click Install model again.")

    def _pull_ollama_model(self, model_name: str, progress_callback=None) -> str:
        body = json.dumps({"name": model_name, "stream": True}).encode("utf-8")
        request = Request(f"{self.ollama_base_url}/api/pull", data=body, headers={"Accept": "application/x-ndjson", "Content-Type": "application/json"}, method="POST")
        last_status = ""
        try:
            with urlopen(request, timeout=60) as response:
                while True:
                    line = response.readline()
                    if not line:
                        break
                    try:
                        payload = json.loads(line.decode("utf-8", errors="replace"))
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(payload, dict):
                        continue
                    if payload.get("error"):
                        raise LocalAIError(f"Ollama could not install {model_name}.\n\n{payload['error']}")
                    status = str(payload.get("status", "")).strip()
                    if status:
                        last_status = status
                    if progress_callback:
                        progress_callback(status or "Downloading…", int(payload.get("completed", 0) or 0), int(payload.get("total", 0) or 0))
            if progress_callback:
                progress_callback("Verifying model…", 0, 0)
            return last_status or f"Ollama installed {model_name}."
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LocalAIError(f"Ollama could not install {model_name}.\n\n{detail or exc.reason}") from exc
        except URLError as exc:
            raise LocalAIError(f"Local Ollama connection error while installing {model_name}: {exc.reason}") from exc
        except TimeoutError as exc:
            raise LocalAIError(f"Ollama timed out while installing {model_name}.") from exc
        except OSError as exc:
            raise LocalAIError(f"Could not communicate with Ollama while installing {model_name}: {exc}") from exc

    def install_models(self, models: tuple[str, ...] | None = None, progress_callback=None) -> str:
        targets = models or self.REQUIRED_OLLAMA_MODELS
        executable = self.ollama_executable
        if not executable:
            raise LocalAIError("Ollama is not installed. Install Ollama, then use this button again.")
        self._ensure_ollama_server(executable)
        existing = set(self.list_models())
        installed: list[str] = []
        for index, model_name in enumerate(targets, 1):
            if model_name in existing:
                if progress_callback:
                    progress_callback(f"Already installed: {model_name} ({index}/{len(targets)})", 0, 0)
                installed.append(model_name)
                continue
            if progress_callback:
                progress_callback(f"Starting download: {model_name} ({index}/{len(targets)})", 0, 0)
            self._pull_ollama_model(model_name, progress_callback=lambda status, completed, total, m=model_name, i=index: progress_callback(f"{m} ({i}/{len(targets)}) — {status}", completed, total) if progress_callback else None)
            installed.append(model_name)
            existing.add(model_name)
        if progress_callback:
            progress_callback("All required local models are installed.", 0, 0)
        return "Installed: " + ", ".join(installed)

    def install_model(self, model: str | None = None, progress_callback=None) -> str:
        requested = (model or "").strip()
        if requested and requested not in self.REQUIRED_OLLAMA_MODELS:
            return self.install_models((requested,), progress_callback=progress_callback)
        return self.install_models(progress_callback=progress_callback)

    def _request(self, method: str, url: str, body: dict | None = None, timeout_seconds: float = 30) -> dict:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
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
