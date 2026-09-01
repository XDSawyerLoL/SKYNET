from __future__ import annotations

import base64
import json
from pathlib import Path
from urllib import request, error


class VisionError(RuntimeError):
    pass


class OllamaVisionClient:
    def __init__(self, base_url: str, model: str | None, timeout: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.model)

    def describe(self, image_path: Path, prompt: str) -> str:
        if not self.model:
            raise VisionError("No SKYNET_VISION_MODEL configured")
        if not image_path.is_file():
            raise VisionError(f"Image not found: {image_path}")
        raw = base64.b64encode(image_path.read_bytes()).decode("ascii")
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [raw],
                }
            ],
        }
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self.base_url + "/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise VisionError(f"Vision request failed: {exc}") from exc
        message = body.get("message") or {}
        content = str(message.get("content") or "").strip()
        if not content:
            raise VisionError("Vision model returned an empty response")
        return content
