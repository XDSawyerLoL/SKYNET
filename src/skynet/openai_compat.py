from __future__ import annotations

import json
from collections.abc import Iterator
from urllib import error, request


class OpenAICompatError(RuntimeError):
    pass


class OpenAICompatibleClient:
    """Tiny dependency-free client for local OpenAI-compatible servers.

    Designed for llama.cpp's local server. It keeps SKYNET independent from
    Ollama while preserving the same message/tool shape expected by Agent.
    """

    def __init__(self, base_url: str, model: str, timeout: int = 180) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def _json(self, method: str, path: str, payload: dict | None = None) -> dict:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        url = f"{self.base_url}{path}"
        req = request.Request(url, data=body, method=method, headers={"Content-Type": "application/json"})
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace").strip()
            except Exception:
                pass
            raise OpenAICompatError(f"Moteur local HTTP {exc.code} sur {url}: {detail}".rstrip()) from exc
        except error.URLError as exc:
            raise OpenAICompatError(f"Moteur local inaccessible sur {self.base_url}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise OpenAICompatError("Réponse JSON invalide du moteur local") from exc

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        *,
        think: bool | None = None,
        num_predict: int | None = None,
    ) -> dict:
        payload: dict = {"model": self.model, "messages": messages, "stream": False}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if num_predict is not None:
            payload["max_tokens"] = max(1, int(num_predict))
        response = self._json("POST", "/chat/completions", payload)
        choices = response.get("choices") or []
        if not choices:
            raise OpenAICompatError(f"Réponse inattendue du moteur local: {response}")
        message = dict(choices[0].get("message") or {})
        if message.get("tool_calls") is None:
            message.pop("tool_calls", None)
        return message

    def warm(self) -> None:
        self.chat([{"role": "user", "content": "Réponds uniquement OK."}], tools=None, num_predict=2)

    def chat_stream(
        self,
        messages: list[dict],
        *,
        think: bool = False,
        num_predict: int = 768,
    ) -> Iterator[str]:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "max_tokens": max(32, int(num_predict)),
        }
        data = json.dumps(payload).encode("utf-8")
        url = f"{self.base_url}/chat/completions"
        req = request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                for raw in response:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_text = line[5:].strip()
                    if data_text == "[DONE]":
                        break
                    try:
                        event = json.loads(data_text)
                    except json.JSONDecodeError:
                        continue
                    choices = event.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    content = str(delta.get("content") or "")
                    if content:
                        yield content
        except error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace").strip()
            except Exception:
                pass
            raise OpenAICompatError(f"Moteur local HTTP {exc.code}: {detail}".rstrip()) from exc
        except error.URLError as exc:
            raise OpenAICompatError(f"Moteur local inaccessible sur {self.base_url}: {exc}") from exc

    def list_models(self) -> list[str]:
        response = self._json("GET", "/models")
        values = response.get("data") or []
        return [str(item.get("id")) for item in values if isinstance(item, dict) and item.get("id")]
