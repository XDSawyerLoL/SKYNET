from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from collections.abc import Callable
from typing import Any

from .audit import AuditLog
from .memory import MemoryStore
from .permissions import PermissionGate
from .skills import SkillStore


class ToolError(RuntimeError):
    pass


class ToolBus:
    def __init__(
        self,
        workspace: Path,
        memory: MemoryStore,
        skills: SkillStore,
        audit: AuditLog,
        permissions: PermissionGate,
    ) -> None:
        self.workspace = workspace.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.memory = memory
        self.skills = skills
        self.audit = audit
        self.permissions = permissions

    def schemas(self) -> list[dict[str, Any]]:
        return [
            self._schema("list_files", "List files inside the allowed workspace.", {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Relative workspace path, default ."}},
            }),
            self._schema("read_file", "Read a UTF-8 text file inside the allowed workspace.", {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            }),
            self._schema("write_file", "Create or replace a UTF-8 text file inside the allowed workspace. Requires user confirmation.", {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            }),
            self._schema("powershell", "Run a PowerShell command on Windows. Requires user confirmation.", {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "integer", "minimum": 1, "maximum": 120}
                },
                "required": ["command"],
            }),
            self._schema("remember", "Store a durable user-approved fact or useful preference in local memory.", {
                "type": "object",
                "properties": {"content": {"type": "string"}},
                "required": ["content"],
            }),
            self._schema("list_skills", "List reusable local skills known by SKYNET.", {
                "type": "object", "properties": {}
            }),
            self._schema("read_skill", "Read one reusable skill by name.", {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            }),
        ]

    @staticmethod
    def _schema(name: str, description: str, parameters: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {"name": name, "description": description, "parameters": parameters},
        }

    def _resolve(self, relative: str) -> Path:
        candidate = (self.workspace / relative).resolve()
        try:
            candidate.relative_to(self.workspace)
        except ValueError as exc:
            raise ToolError("Path escapes the configured workspace") from exc
        return candidate

    def _summary(self, name: str, args: dict[str, Any]) -> str:
        if name == "write_file":
            return f"Allow SKYNET to write {args.get('path', '?')}?"
        if name == "powershell":
            return f"Allow PowerShell command?\n{args.get('command', '')}"
        return f"Allow tool {name}?"

    def execute(
        self,
        name: str,
        args: dict[str, Any],
        confirmer: Callable[[str], bool],
    ) -> str:
        if not self.permissions.authorize(name, self._summary(name, args), confirmer):
            self.audit.record(name, self._audit_args(name, args), "denied")
            return "DENIED BY USER/POLICY"

        try:
            if name == "list_files":
                result = self._list_files(str(args.get("path", ".")))
            elif name == "read_file":
                result = self._read_file(str(args["path"]))
            elif name == "write_file":
                result = self._write_file(str(args["path"]), str(args["content"]))
            elif name == "powershell":
                result = self._powershell(str(args["command"]), int(args.get("timeout", 60)))
            elif name == "remember":
                result = self.memory.remember(str(args["content"]))
            elif name == "list_skills":
                result = json.dumps(self.skills.list_skills(), ensure_ascii=False)
            elif name == "read_skill":
                result = self.skills.read_skill(str(args["name"]))
            else:
                raise ToolError(f"Unknown tool: {name}")
            self.audit.record(name, self._audit_args(name, args), "ok")
            return result
        except Exception as exc:
            self.audit.record(name, self._audit_args(name, args), f"error:{type(exc).__name__}")
            return f"TOOL ERROR: {exc}"

    def _audit_args(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        clean = dict(args)
        if name == "write_file" and "content" in clean:
            clean["content"] = f"<redacted {len(str(clean['content']))} chars>"
        return clean

    def _list_files(self, relative: str) -> str:
        path = self._resolve(relative)
        if not path.exists():
            raise FileNotFoundError(relative)
        if path.is_file():
            return str(path.relative_to(self.workspace))
        items: list[str] = []
        for child in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:200]:
            suffix = "/" if child.is_dir() else ""
            items.append(str(child.relative_to(self.workspace)) + suffix)
        return "\n".join(items) if items else "<empty>"

    def _read_file(self, relative: str) -> str:
        path = self._resolve(relative)
        if not path.is_file():
            raise FileNotFoundError(relative)
        if path.stat().st_size > 200_000:
            raise ToolError("File exceeds V0.1 text read limit (200 KB)")
        return path.read_text(encoding="utf-8")

    def _write_file(self, relative: str, content: str) -> str:
        path = self._resolve(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Wrote {path.relative_to(self.workspace)} ({len(content)} chars)"

    def _powershell(self, command: str, timeout: int) -> str:
        if os.name != "nt":
            raise ToolError("PowerShell tool is enabled only on Windows in V0.1")
        completed = subprocess.run(
            ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
            cwd=self.workspace,
            capture_output=True,
            text=True,
            timeout=max(1, min(timeout, 120)),
            shell=False,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        output = output.strip()
        if len(output) > 30_000:
            output = output[-30_000:]
        return f"exit_code={completed.returncode}\n{output}".strip()
