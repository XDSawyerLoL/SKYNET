from __future__ import annotations

import json
from urllib import request, error
from collections.abc import Iterator


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout: int = 180, keep_alive: str = "30m") -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.keep_alive = keep_alive

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
            self._raise_http_error(exc, url, path)
            raise AssertionError("unreachable")
        except error.URLError as exc:
            raise OllamaError(
                f"Ollama inaccessible at {self.base_url}: {exc}. "
                "Vérifie qu'Ollama est installé et lancé."
            ) from exc
        except json.JSONDecodeError as exc:
            raise OllamaError("Invalid JSON returned by Ollama") from exc

    def _raise_http_error(self, exc: error.HTTPError, url: str, path: str) -> None:
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

    def warm(self) -> None:
        """Load the model into Ollama without generating user-visible text."""
        self._json(
            "POST",
            "/api/generate",
            {"model": self.model, "prompt": "", "stream": False, "keep_alive": self.keep_alive},
        )

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        *,
        think: bool | None = None,
        num_predict: int | None = None,
    ) -> dict:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": self.keep_alive,
        }
        if tools:
            payload["tools"] = tools
        if think is not None:
            payload["think"] = bool(think)
        if num_predict is not None:
            payload["options"] = {"num_predict": max(32, int(num_predict))}
        response = self._json("POST", "/api/chat", payload)
        if "message" not in response:
            raise OllamaError(f"Unexpected Ollama response: {response}")
        return response["message"]

    def chat_stream(
        self,
        messages: list[dict],
        *,
        think: bool = False,
        num_predict: int = 768,
    ) -> Iterator[str]:
        """Yield visible text as Ollama generates it."""

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "keep_alive": self.keep_alive,
            "think": bool(think),
            "options": {"num_predict": max(32, int(num_predict))},
        }
        data = json.dumps(payload).encode("utf-8")
        url = f"{self.base_url}/api/chat"
        req = request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                for raw in response:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        event = json.loads(raw.decode("utf-8"))
                    except json.JSONDecodeError:
                        continue
                    if event.get("error"):
                        raise OllamaError(str(event["error"]))
                    message = event.get("message") or {}
                    content = str(message.get("content") or "")
                    if content:
                        yield content
                    if event.get("done"):
                        break
        except error.HTTPError as exc:
            self._raise_http_error(exc, url, "/api/chat")
        except error.URLError as exc:
            raise OllamaError(
                f"Ollama inaccessible at {self.base_url}: {exc}. Vérifie qu'Ollama est lancé."
            ) from exc

    def list_models(self) -> list[str]:
        response = self._json("GET", "/api/tags")
        return [m.get("name", "") for m in response.get("models", []) if m.get("name")]
