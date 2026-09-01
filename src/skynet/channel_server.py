from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import json
import os
import threading

from .runtime import Runtime


class ChannelBridge:
    """Opt-in loopback webhook bridge for external channel adapters.

    It never starts automatically. A bearer token is required. Incoming remote
    messages run with unattended confirmation behavior, so sensitive actions are
    denied rather than remotely self-approved.
    """

    def __init__(self, root: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.root = root.resolve(); self.host = host; self.port = int(port)
        self.token = os.getenv("SKYNET_WEBHOOK_TOKEN", "").strip()
        if len(self.token) < 16:
            raise RuntimeError("Set SKYNET_WEBHOOK_TOKEN to a random value of at least 16 characters before starting the channel bridge")
        self.runtime = Runtime.create(self.root, session_id="channel-bridge")
        self.stop_event = threading.Event()

    def _handler(self):
        bridge = self
        class Handler(BaseHTTPRequestHandler):
            server_version = "SKYNETChannel/0.9"
            def _json(self, code: int, payload: dict) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
            def _authorized(self) -> bool:
                return self.headers.get("Authorization", "") == f"Bearer {bridge.token}"
            def do_GET(self) -> None:  # noqa: N802
                parsed = urlsplit(self.path)
                if parsed.path == "/health":
                    self._json(200, {"status": "ok", "pending": len(bridge.runtime.channels.pending())}); return
                if not self._authorized(): self._json(401, {"error": "unauthorized"}); return
                if parsed.path == "/outbox":
                    self._json(200, {"messages": [bridge._message_json(x) for x in bridge.runtime.channels.outbox()]}); return
                self._json(404, {"error": "not found"})
            def do_POST(self) -> None:  # noqa: N802
                if not self._authorized(): self._json(401, {"error": "unauthorized"}); return
                parsed = urlsplit(self.path); parts = [x for x in parsed.path.split("/") if x]
                if len(parts) != 3 or parts[0] != "inbound":
                    self._json(404, {"error": "use POST /inbound/<channel>/<peer>?session=<id>"}); return
                try:
                    length = min(int(self.headers.get("Content-Length", "0")), 200_000)
                    raw = self.rfile.read(length); data = json.loads(raw.decode("utf-8")) if raw else {}
                    content = str(data.get("content", ""))
                    session = parse_qs(parsed.query).get("session", [f"{parts[1]}:{parts[2]}"])[0]
                    item = bridge.runtime.channels.receive(parts[1], parts[2], content, session)
                    bridge.runtime.sessions.ensure(session, title=f"{parts[1]} · {parts[2]}", channel=parts[1])
                    self._json(202, {"message_id": item.message_id, "session_id": item.session_id})
                except Exception as exc:
                    self._json(400, {"error": f"{type(exc).__name__}: {exc}"})
            def log_message(self, format: str, *args) -> None: return
        return Handler

    @staticmethod
    def _message_json(item) -> dict:
        return {"message_id": item.message_id, "direction": item.direction, "channel": item.channel,
                "peer": item.peer, "session_id": item.session_id, "content": item.content,
                "status": item.status, "created_at": item.created_at}

    def _worker(self) -> None:
        while not self.stop_event.is_set():
            for item in self.runtime.channels.pending(limit=20):
                denied = False
                def deny_sensitive(_: str) -> bool:
                    nonlocal denied
                    denied = True
                    return False
                try:
                    reply = self.runtime.agent.ask_in_session(
                        item.session_id,
                        item.content,
                        deny_sensitive,
                        title=f"{item.channel} · {item.peer}",
                        channel=item.channel,
                    )
                    if denied:
                        reply += "\n\n[SKYNET] A sensitive action was not executed because remote channel sessions cannot self-approve it."
                    self.runtime.channels.send(item.channel, item.peer, reply, item.session_id)
                    self.runtime.channels.mark(item.message_id, "processed")
                except Exception as exc:
                    self.runtime.channels.mark(item.message_id, f"error:{type(exc).__name__}")
            self.stop_event.wait(1.0)

    def run(self) -> None:
        worker = threading.Thread(target=self._worker, daemon=True, name="skynet-channel-worker"); worker.start()
        server = ThreadingHTTPServer((self.host, self.port), self._handler())
        try:
            print(f"SKYNET channel bridge listening on http://{self.host}:{self.port} (opt-in, bearer auth required)")
            server.serve_forever(poll_interval=0.5)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop_event.set(); server.shutdown(); server.server_close(); worker.join(timeout=3); self.runtime.close()


def main() -> None:
    host = os.getenv("SKYNET_CHANNEL_HOST", "127.0.0.1")
    if host not in {"127.0.0.1", "localhost", "::1"} and os.getenv("SKYNET_ALLOW_REMOTE_CHANNEL_BIND", "0") != "1":
        raise SystemExit("Refusing non-loopback channel bind. Set SKYNET_ALLOW_REMOTE_CHANNEL_BIND=1 explicitly to override.")
    ChannelBridge(Path.cwd(), host=host, port=int(os.getenv("SKYNET_CHANNEL_PORT", "8765"))).run()


if __name__ == "__main__":
    main()
