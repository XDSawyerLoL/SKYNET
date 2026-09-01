from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
from typing import Any


class MCPError(RuntimeError):
    pass


@dataclass(slots=True)
class MCPServerSpec:
    command: str
    args: list[str]
    env: dict[str, str]


class MCPStdioSession:
    """Minimal MCP stdio JSON-RPC client with no third-party dependency."""

    def __init__(self, name: str, spec: MCPServerSpec, timeout: int = 30) -> None:
        self.name = name
        self.spec = spec
        self.timeout = timeout
        env = os.environ.copy()
        env.update(spec.env)
        self.process = subprocess.Popen(
            [spec.command, *spec.args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=env,
        )
        if self.process.stdin is None or self.process.stdout is None:
            raise MCPError(f"Failed to open stdio for MCP server {name}")
        self._next_id = 1
        self._responses: queue.Queue[dict[str, Any]] = queue.Queue()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self._initialize()

    def _read_loop(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                self._responses.put(payload)

    def _send(self, payload: dict[str, Any]) -> None:
        if self.process.poll() is not None:
            raise MCPError(f"MCP server {self.name} exited with code {self.process.returncode}")
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        self.process.stdin.flush()

    def _request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        req_id = self._next_id
        self._next_id += 1
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            payload["params"] = params
        self._send(payload)
        while True:
            try:
                response = self._responses.get(timeout=self.timeout)
            except queue.Empty as exc:
                raise MCPError(f"Timeout waiting for {method} from {self.name}") from exc
            if response.get("id") != req_id:
                continue
            if "error" in response:
                raise MCPError(f"{method} failed: {response['error']}")
            return response.get("result")

    def _initialize(self) -> None:
        self._request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "SKYNET", "version": "0.2.0"},
            },
        )
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def list_tools(self) -> list[dict[str, Any]]:
        result = self._request("tools/list", {})
        if not isinstance(result, dict):
            return []
        tools = result.get("tools")
        return tools if isinstance(tools, list) else []

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        return self._request("tools/call", {"name": name, "arguments": arguments})

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()


class MCPHub:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self._specs = self._load_specs()
        self._sessions: dict[str, MCPStdioSession] = {}

    def _load_specs(self) -> dict[str, MCPServerSpec]:
        if not self.config_path.exists():
            return {}
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        raw_servers = data.get("servers", {}) if isinstance(data, dict) else {}
        specs: dict[str, MCPServerSpec] = {}
        if not isinstance(raw_servers, dict):
            return specs
        for name, raw in raw_servers.items():
            if not isinstance(name, str) or not isinstance(raw, dict):
                continue
            command = raw.get("command")
            args = raw.get("args", [])
            env = raw.get("env", {})
            if not isinstance(command, str) or not command:
                continue
            if not isinstance(args, list) or not all(isinstance(x, str) for x in args):
                continue
            if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
                continue
            specs[name] = MCPServerSpec(command, list(args), dict(env))
        return specs

    def list_servers(self) -> list[str]:
        return sorted(self._specs)

    def _session(self, name: str) -> MCPStdioSession:
        if name not in self._specs:
            raise MCPError(f"Unknown MCP server: {name}")
        session = self._sessions.get(name)
        if session is None or session.process.poll() is not None:
            session = MCPStdioSession(name, self._specs[name])
            self._sessions[name] = session
        return session

    def list_tools(self, server: str) -> list[dict[str, Any]]:
        return self._session(server).list_tools()

    def call(self, server: str, tool: str, arguments: dict[str, Any]) -> Any:
        return self._session(server).call_tool(tool, arguments)

    def close(self) -> None:
        for session in self._sessions.values():
            session.close()
        self._sessions.clear()
