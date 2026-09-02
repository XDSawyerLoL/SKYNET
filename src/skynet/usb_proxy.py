from __future__ import annotations

import copy
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import error, request


USB_MODEL = "qwen3:4b-usb"


def tags_payload(model: str = USB_MODEL) -> dict:
    return {"models": [{"name": model, "model": model, "details": {"family": "qwen3", "quantization_level": "Q4_K_M"}}]}


def _without_thinking(messages: list[dict]) -> list[dict]:
    """Use Qwen3's documented soft switch to keep portable chat responsive."""
    clean = copy.deepcopy(messages)
    for item in reversed(clean):
        if item.get("role") == "user" and isinstance(item.get("content"), str):
            content = str(item["content"])
            if "/think" not in content and "/no_think" not in content:
                item["content"] = content.rstrip() + "\n/no_think"
            break
    return clean


def openai_payload_from_ollama(payload: dict, model: str = USB_MODEL) -> dict:
    options = payload.get("options") or {}
    result: dict = {
        "model": model,
        "messages": _without_thinking(list(payload.get("messages") or [])),
        "stream": bool(payload.get("stream", False)),
        "temperature": 0.7,
        "top_p": 0.8,
    }
    if options.get("num_predict") is not None:
        result["max_tokens"] = max(32, int(options["num_predict"]))
    if payload.get("tools"):
        result["tools"] = payload["tools"]
        result["tool_choice"] = "auto"
    return result


def ollama_message_from_openai(response: dict) -> dict:
    choices = response.get("choices") or []
    message = dict((choices[0].get("message") if choices else None) or {})
    message.setdefault("role", "assistant")
    message.setdefault("content", "")
    return message


def stream_event_from_openai(event: dict) -> dict | None:
    choices = event.get("choices") or []
    if not choices:
        return None
    delta = choices[0].get("delta") or {}
    content = str(delta.get("content") or "")
    if not content:
        return None
    return {"message": {"role": "assistant", "content": content}, "done": False}


class USBProxy:
    """Expose the minimal Ollama HTTP contract SKYNET already consumes.

    The actual inference process is llama.cpp on another loopback port. This
    adapter keeps the mature SKYNET routing/agent code unchanged.
    """

    def __init__(self, host: str, port: int, llama_base_url: str, model: str = USB_MODEL) -> None:
        self.host = host
        self.port = int(port)
        self.llama_base_url = llama_base_url.rstrip("/")
        self.model = model
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "SKYNET-USB/1"

            def log_message(self, _format: str, *_args) -> None:
                return

            def _read_json(self) -> dict:
                length = int(self.headers.get("Content-Length") or "0")
                raw = self.rfile.read(length) if length else b"{}"
                return json.loads(raw.decode("utf-8"))

            def _json(self, status: int, payload: dict) -> None:
                raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self) -> None:  # noqa: N802
                if self.path.rstrip("/") == "/api/tags":
                    self._json(200, tags_payload(owner.model))
                    return
                self._json(404, {"error": "endpoint unavailable"})

            def do_POST(self) -> None:  # noqa: N802
                try:
                    payload = self._read_json()
                    if self.path.rstrip("/") == "/api/generate":
                        # llama.cpp loads the model at server startup, so Ollama's
                        # keep-alive warm-up request can complete immediately.
                        self._json(200, {"model": owner.model, "response": "", "done": True})
                        return
                    if self.path.rstrip("/") != "/api/chat":
                        self._json(404, {"error": "endpoint unavailable"})
                        return
                    if bool(payload.get("stream", False)):
                        self._chat_stream(payload)
                    else:
                        self._chat_once(payload)
                except Exception as exc:
                    try:
                        self._json(500, {"error": f"{type(exc).__name__}: {exc}"})
                    except Exception:
                        pass

            def _upstream(self, payload: dict, *, stream: bool):
                body = json.dumps(openai_payload_from_ollama(payload, owner.model)).encode("utf-8")
                req = request.Request(
                    f"{owner.llama_base_url}/v1/chat/completions",
                    data=body,
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                return request.urlopen(req, timeout=240 if stream else 180)

            def _chat_once(self, payload: dict) -> None:
                try:
                    with self._upstream(payload, stream=False) as response:
                        data = json.loads(response.read().decode("utf-8"))
                    self._json(200, {"model": owner.model, "message": ollama_message_from_openai(data), "done": True})
                except error.HTTPError as exc:
                    detail = exc.read().decode("utf-8", errors="replace")
                    self._json(exc.code, {"error": detail or str(exc)})

            def _chat_stream(self, payload: dict) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                try:
                    with self._upstream(payload, stream=True) as response:
                        for raw in response:
                            line = raw.decode("utf-8", errors="replace").strip()
                            if not line.startswith("data:"):
                                continue
                            value = line[5:].strip()
                            if value == "[DONE]":
                                break
                            try:
                                event = json.loads(value)
                            except json.JSONDecodeError:
                                continue
                            translated = stream_event_from_openai(event)
                            if translated is not None:
                                self.wfile.write((json.dumps(translated, ensure_ascii=False) + "\n").encode("utf-8"))
                                self.wfile.flush()
                    final = {"model": owner.model, "message": {"role": "assistant", "content": ""}, "done": True}
                    self.wfile.write((json.dumps(final, ensure_ascii=False) + "\n").encode("utf-8"))
                    self.wfile.flush()
                except Exception as exc:
                    failure = {"error": f"{type(exc).__name__}: {exc}", "done": True}
                    self.wfile.write((json.dumps(failure, ensure_ascii=False) + "\n").encode("utf-8"))
                    self.wfile.flush()

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True, name="skynet-usb-proxy")
        self._thread.start()

    def close(self) -> None:
        server = self._server
        self._server = None
        if server is not None:
            server.shutdown()
            server.server_close()
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=2)
