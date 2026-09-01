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
        url = f"{self.base_url}{path}"
        req = request.Request(
            url,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace").strip()
            except Exception:
                pass
            detail = body
            try:
                parsed = json.loads(body) if body else {}
                if isinstance(parsed, dict) and parsed.get("error"):
                    detail = str(parsed["error"])
            except json.JSONDecodeError:
                pass

            lower = detail.casefold()
            if exc.code == 404 and path == "/api/chat" and "model" in lower and "not found" in lower:
                raise OllamaError(
                    f"Le modèle Ollama '{self.model}' n'est pas installé. "
                    f"Installe-le avec : ollama pull {self.model}"
                ) from exc

            suffix = f": {detail}" if detail else ""
            raise OllamaError(f"Ollama HTTP {exc.code} at {url}{suffix}") from exc
        except error.URLError as exc:
            raise OllamaError(
                f"Ollama inaccessible at {self.base_url}: {exc}. "
                "Vérifie qu'Ollama est installé et lancé."
            ) from exc
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
