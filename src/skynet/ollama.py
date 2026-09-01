from __future__ import annotations

import json
from urllib import request, error


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout: int = 180) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def _json(self, method: str, path: str, payload: dict | None = None) -> dict:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.URLError as exc:
            raise OllamaError(f"Ollama inaccessible at {self.base_url}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise OllamaError("Invalid JSON returned by Ollama") from exc

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        response = self._json("POST", "/api/chat", payload)
        if "message" not in response:
            raise OllamaError(f"Unexpected Ollama response: {response}")
        return response["message"]

    def list_models(self) -> list[str]:
        response = self._json("GET", "/api/tags")
        return [m.get("name", "") for m in response.get("models", []) if m.get("name")]
