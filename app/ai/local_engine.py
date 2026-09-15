"""Optional local AI engine for lightweight offline tasks."""

from __future__ import annotations

import base64
import io
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LocalAIError(RuntimeError):
    pass


class LocalAIEngine:
    """Local AI client with Ollama support, fast text, quality text, and vision routing."""

    DEFAULT_BASE_URL = "http://localhost:11434/v1"
    DEFAULT_MODEL = "qwen3:1.7b"
    FAST_MODEL = "qwen3:1.7b"
    QUALITY_MODEL = "qwen3:4b"
    VISION_MODEL = "qwen3-vl:2b-instruct"
    REQUIRED_OLLAMA_MODELS = (FAST_MODEL, QUALITY_MODEL, VISION_MODEL)
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
            missing = [name for name in self.REQUIRED_OLLAMA_MODELS if name not in models] if self.is_ollama_endpoint else []
            reason = "Local AI is ready." if not missing else f"Missing local models: {', '.join(missing)}"
            return {"enabled": True, "available": bool(models), "ollama_installed": bool(self.ollama_executable), "models": models, "model": selected, "missing_models": missing, "vision_model": self._find_installed_vision_model(models), "reason": reason}
        except Exception as exc:
            installed = bool(self.ollama_executable)
            return {"enabled": True, "available": False, "ollama_installed": installed, "models": [], "model": self.model, "missing_models": list(self.REQUIRED_OLLAMA_MODELS) if self.is_ollama_endpoint else [], "vision_model": "", "reason": str(exc) if installed or not self.is_ollama_endpoint else "Ollama is not installed or not running."}

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

    @classmethod
    def _find_installed_vision_model(cls, models: list[str]) -> str:
        if cls.VISION_MODEL in models:
            return cls.VISION_MODEL
        for model in models:
            if model.startswith("qwen3-vl:"):
                return model
        return ""

    def resolve_model(self) -> str:
        models = self.list_models()
        if self.model and self.model in models:
            return self.model
        for preferred in (self.FAST_MODEL, self.QUALITY_MODEL):
            if preferred in models:
                return preferred
        blocked = ("embedding", "moderation", "image", "audio", "tts", "whisper", "qwen3-vl")
        for model in models:
            if not any(token in model.lower() for token in blocked):
                return model
        raise LocalAIError("No suitable local text model is installed.")

    def resolve_vision_model(self) -> str:
        models = self.list_models()
        selected = self._find_installed_vision_model(models)
        if selected:
            return selected
        raise LocalAIError(f"No local vision model is installed. Install {self.VISION_MODEL} from Settings first.")

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
            return max(32, min(int(os.getenv("LOCAL_AI_MAX_TOKENS", "128")), 512))
        except (TypeError, ValueError):
            return 128

    def _request_options(self, *, vision: bool = False) -> dict[str, object]:
        if not self.is_ollama_endpoint:
            return {}
        ctx = self._num_ctx()
        if vision:
            ctx = max(ctx, 8192)
        return {"num_ctx": ctx, "temperature": 0.2, "num_predict": self._max_tokens()}

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
        if not self.enabled:
            raise LocalAIError("Local AI is disabled.")
        encoded = base64.b64encode(self._image_bytes(image)).decode("ascii")
        model = self.resolve_vision_model() if self.is_ollama_endpoint else self.resolve_model()
        if self.is_ollama_endpoint:
            body = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "Return only valid JSON."},
                    {"role": "user", "content": prompt, "images": [encoded]},
                ],
                "stream": False,
                "think": self._thinking_enabled(),
                "keep_alive": self._keep_alive(),
                "options": self._request_options(vision=True),
            }
            data = self._request("POST", f"{self.ollama_base_url}/api/chat", body, timeout_seconds=180)
            try:
                raw = str(data["message"]["content"]).strip()
            except (KeyError, TypeError) as exc:
                raise LocalAIError("The local vision model returned an unsupported response.") from exc
        else:
            body = {"model": model, "messages": [{"role": "system", "content": "Return only valid JSON."}, {"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}}]}], "stream": False}
            data = self._request("POST", f"{self.base_url}/chat/completions", body)
            try:
                raw = str(data["choices"][0]["message"]["content"]).strip()
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

    def _ensure_ollama_server(self, executable: str) -> None:
        """Ensure Ollama is available without spawning a console window."""
        try:
            request = Request(f"{self.ollama_base_url}/api/tags", headers={"Accept": "application/json"}, method="GET")
            with urlopen(request, timeout=1.5):
                return
        except (HTTPError, URLError, TimeoutError, OSError):
            pass
        raise LocalAIError("Ollama is installed, but its local service is not running. Start Ollama from Windows, then click Install model again.")

    def _pull_ollama_model(self, model_name: str, progress_callback=None) -> str:
        body = json.dumps({"name": model_name, "stream": True}).encode("utf-8")
        request = Request(
            f"{self.ollama_base_url}/api/pull",
            data=body,
            headers={"Accept": "application/x-ndjson", "Content-Type": "application/json"},
            method="POST",
        )
        last_status = ""
        try:
            with urlopen(request, timeout=30) as response:
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
                    if progress_callback is not None:
                        try:
                            completed = int(payload.get("completed", 0) or 0)
                            total = int(payload.get("total", 0) or 0)
                            progress_callback(status or "Downloading…", completed, total)
                        except (TypeError, ValueError):
                            pass
            if progress_callback is not None:
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
        """Install all required local models for text, quality, and visual desktop tasks."""
        targets = models or self.REQUIRED_OLLAMA_MODELS
        executable = self.ollama_executable
        if not executable:
            raise LocalAIError("Ollama is not installed. Install Ollama, then use this button again.")
        self._ensure_ollama_server(executable)
        if not self.is_ollama_endpoint:
            raise LocalAIError("Installing the bundled local models requires an Ollama endpoint at localhost:11434.")

        installed: list[str] = []
        existing = set(self.list_models()) if self._server_is_available() else set()
        for index, model_name in enumerate(targets, 1):
            if model_name in existing:
                if progress_callback is not None:
                    progress_callback(f"Already installed: {model_name} ({index}/{len(targets)})", 0, 0)
                installed.append(model_name)
                continue
            if progress_callback is not None:
                progress_callback(f"Starting download: {model_name} ({index}/{len(targets)})", 0, 0)

            def report(status: str, completed: int, total: int, model=model_name, idx=index) -> None:
                label = f"{model} ({idx}/{len(targets)}) — {status}"
                if progress_callback is not None:
                    progress_callback(label, completed, total)

            self._pull_ollama_model(model_name, progress_callback=report)
            installed.append(model_name)
            existing.add(model_name)

        if progress_callback is not None:
            progress_callback("All required local models are installed.", 0, 0)
        return "Installed: " + ", ".join(installed)

    def install_model(self, model: str | None = None, progress_callback=None) -> str:
        """Backward-compatible installer; Settings now installs the full local bundle."""
        if self.is_ollama_endpoint:
            requested = (model or "").strip()
            if requested and requested not in self.REQUIRED_OLLAMA_MODELS:
                return self.install_models((requested,), progress_callback=progress_callback)
            return self.install_models(progress_callback=progress_callback)
        model_name = (model or self.model or self.DEFAULT_MODEL).strip()
        if not model_name:
            raise LocalAIError("Enter a local model name first.")
        executable = self.ollama_executable
        if not executable:
            raise LocalAIError("Ollama is not installed. Install Ollama, then use this button again.")
        raise LocalAIError("The bundled local model installer requires Ollama at localhost:11434.")

    def _server_is_available(self) -> bool:
        try:
            request = Request(f"{self.ollama_base_url}/api/tags", headers={"Accept": "application/json"}, method="GET")
            with urlopen(request, timeout=1.5):
                return True
        except (HTTPError, URLError, TimeoutError, OSError):
            return False

    @staticmethod
    def _image_bytes(image) -> bytes:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def _request(self, method: str, url: str, body: dict | None = None, timeout_seconds: float | None = None) -> dict:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers, method=method)
        timeout = timeout_seconds if timeout_seconds is not None else (4 if body is None else 45)
        try:
            with urlopen(request, timeout=timeout) as response:
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
