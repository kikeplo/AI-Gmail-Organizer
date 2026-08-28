"""Local vision fallback for screenshot understanding.

Uses an Ollama-compatible local multimodal endpoint when available. The cloud
provider can remain text-only while a local vision model handles screenshots.
"""

from __future__ import annotations

import base64
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LocalVisionError(RuntimeError):
    pass


class LocalVisionEngine:
    def __init__(self) -> None:
        self.base_url = os.getenv("LOCAL_VISION_BASE_URL", "http://localhost:11434/api").strip().rstrip("/")
        self.model = os.getenv("LOCAL_VISION_MODEL", "").strip()
        self.enabled = os.getenv("LOCAL_VISION_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}

    def available(self) -> bool:
        if not self.enabled or not self.model:
            return False
        try:
            request = Request(f"{self.base_url}/tags", headers={"Accept": "application/json"}, method="GET")
            with urlopen(request, timeout=4) as response:
                data = json.loads(response.read().decode("utf-8"))
            names = {str(item.get("name", "")) for item in data.get("models", []) if isinstance(item, dict)}
            return self.model in names
        except Exception:
            return False

    def analyze(self, prompt: str, image) -> dict:
        if not self.enabled:
            raise LocalVisionError("Local vision is disabled.")
        if not self.model:
            raise LocalVisionError("No local vision model is configured.")
        encoded = self._encode(image)
        body = {
            "model": self.model,
            "prompt": prompt,
            "images": [encoded],
            "stream": False,
            "format": "json",
        }
        data = self._request("POST", f"{self.base_url}/generate", body)
        raw = str(data.get("response", "")).strip().replace("```json", "").replace("```", "").strip()
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LocalVisionError("The local vision model did not return valid JSON.") from exc
        if not isinstance(result, dict):
            raise LocalVisionError("The local vision model returned an invalid action format.")
        return result

    @staticmethod
    def _encode(image) -> str:
        import io
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("ascii")

    @staticmethod
    def _request(method: str, url: str, body: dict) -> dict:
        data = json.dumps(body).encode("utf-8")
        request = Request(url, data=data, headers={"Accept": "application/json", "Content-Type": "application/json"}, method=method)
        try:
            with urlopen(request, timeout=45) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LocalVisionError(f"Local vision HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise LocalVisionError(f"Local vision connection error: {exc.reason}") from exc
