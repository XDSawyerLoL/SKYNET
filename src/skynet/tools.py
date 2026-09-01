from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from collections.abc import Callable
from typing import Any

from .audit import AuditLog
from .mcp import MCPHub
from .memory import MemoryStore
from .permissions import PermissionGate
from .planning import PlanStore
from .skills import SkillStore
from .vision import OllamaVisionClient
from .windows import WindowsController


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
        plans: PlanStore | None = None,
        windows: WindowsController | None = None,
        mcp: MCPHub | None = None,
        vision: OllamaVisionClient | None = None,
    ) -> None:
        self.workspace = workspace.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.memory = memory
        self.skills = skills
        self.audit = audit
        self.permissions = permissions
        self.plans = plans
        self.windows = windows
        self.mcp = mcp
        self.vision = vision

    def schemas(self) -> list[dict[str, Any]]:
        schemas = [
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
            self._schema("remember", "Store a durable useful fact or preference in local memory. Never store secrets.", {
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
            self._schema("save_skill", "Save a successful reusable procedure as a local Markdown skill. Requires confirmation.", {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "content": {"type": "string", "description": "Include purpose, preconditions, steps, verification and recovery."},
                },
                "required": ["name", "content"],
            }),
        ]
        if self.plans is not None:
            schemas += [
                self._schema("create_plan", "Create a structured local execution plan for a multi-step task.", {
                    "type": "object",
                    "properties": {
                        "goal": {"type": "string"},
                        "steps": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 20},
                    },
                    "required": ["goal", "steps"],
                }),
                self._schema("update_plan", "Update one plan step with status and evidence.", {
                    "type": "object",
                    "properties": {
                        "plan_id": {"type": "string"},
                        "step": {"type": "integer", "minimum": 1},
                        "status": {"type": "string", "enum": ["pending", "running", "done", "failed", "skipped"]},
                        "evidence": {"type": "string"},
                    },
                    "required": ["plan_id", "step", "status"],
                }),
            ]
        if self.windows is not None:
            schemas += [
                self._schema("windows_list", "List visible top-level Windows application windows. Read-only.", {
                    "type": "object", "properties": {}
                }),
                self._schema("windows_accessibility", "Inspect the Windows UI Automation accessibility tree around the focused application. Read-only.", {
                    "type": "object",
                    "properties": {"max_nodes": {"type": "integer", "minimum": 1, "maximum": 250}},
                }),
                self._schema("windows_focus", "Focus a visible application window by partial title. Requires confirmation.", {
                    "type": "object",
                    "properties": {"title": {"type": "string"}},
                    "required": ["title"],
                }),
                self._schema("windows_invoke", "Invoke a named UI Automation element in the focused window. Requires confirmation.", {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                }),
                self._schema("windows_type", "Paste text into the currently focused Windows control. Requires confirmation.", {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                }),
                self._schema("windows_screenshot", "Capture the Windows virtual screen to a PNG inside the workspace. Requires confirmation.", {
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": "Relative .png path inside workspace"}},
                }),
            ]
            if self.vision is not None and self.vision.enabled:
                schemas.append(
                    self._schema("vision_describe", "Ask the configured local vision model to inspect a workspace PNG screenshot.", {
                        "type": "object",
                        "properties": {"path": {"type": "string"}, "prompt": {"type": "string"}},
                        "required": ["path", "prompt"],
                    })
                )
        if self.mcp is not None:
            schemas += [
                self._schema("mcp_list_servers", "List configured local MCP servers.", {
                    "type": "object", "properties": {}
                }),
                self._schema("mcp_list_tools", "List tools exposed by a configured local MCP server.", {
                    "type": "object",
                    "properties": {"server": {"type": "string"}},
                    "required": ["server"],
                }),
                self._schema("mcp_call", "Call a tool on a local MCP server. Requires confirmation.", {
                    "type": "object",
                    "properties": {
                        "server": {"type": "string"},
                        "tool": {"type": "string"},
                        "arguments": {"type": "object"},
                    },
                    "required": ["server", "tool", "arguments"],
                }),
            ]
        return schemas

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
        if name == "save_skill":
            return f"Allow SKYNET to save reusable skill {args.get('name', '?')}?"
        if name == "windows_focus":
            return f"Allow SKYNET to focus window matching: {args.get('title', '?')}"
        if name == "windows_invoke":
            return f"Allow SKYNET to activate UI element: {args.get('name', '?')}"
        if name == "windows_type":
            return f"Allow SKYNET to type/paste {len(str(args.get('text', '')))} characters into the focused app?"
        if name == "windows_screenshot":
            return f"Allow SKYNET to capture the current screen to {args.get('path', 'screenshots/latest.png')}?"
        if name == "mcp_call":
            return f"Allow MCP call {args.get('server', '?')}::{args.get('tool', '?')}?"
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
            result = self._dispatch(name, args)
            self.audit.record(name, self._audit_args(name, args), "ok")
            return result
        except Exception as exc:
            self.audit.record(name, self._audit_args(name, args), f"error:{type(exc).__name__}")
            return f"TOOL ERROR: {exc}"

    def _dispatch(self, name: str, args: dict[str, Any]) -> str:
        if name == "list_files":
            return self._list_files(str(args.get("path", ".")))
        if name == "read_file":
            return self._read_file(str(args["path"]))
        if name == "write_file":
            return self._write_file(str(args["path"]), str(args["content"]))
        if name == "powershell":
            return self._powershell(str(args["command"]), int(args.get("timeout", 60)))
        if name == "remember":
            return self.memory.remember(str(args["content"]))
        if name == "list_skills":
            return json.dumps(self.skills.list_skills(), ensure_ascii=False)
        if name == "read_skill":
            return self.skills.read_skill(str(args["name"]))
        if name == "save_skill":
            return self.skills.save_skill(str(args["name"]), str(args["content"]))

        if name == "create_plan" and self.plans is not None:
            plan = self.plans.create(str(args["goal"]), list(args["steps"]))
            return self.plans.render(plan)
        if name == "update_plan" and self.plans is not None:
            plan = self.plans.update(
                str(args["plan_id"]),
                int(args["step"]),
                str(args["status"]),
                str(args.get("evidence", "")),
            )
            return self.plans.render(plan)

        if name == "windows_list" and self.windows is not None:
            return self.windows.list_windows()
        if name == "windows_accessibility" and self.windows is not None:
            return self.windows.accessibility_snapshot(int(args.get("max_nodes", 100)))
        if name == "windows_focus" and self.windows is not None:
            return self.windows.focus_window(str(args["title"]))
        if name == "windows_invoke" and self.windows is not None:
            return self.windows.invoke_element(str(args["name"]))
        if name == "windows_type" and self.windows is not None:
            return self.windows.type_text(str(args["text"]))
        if name == "windows_screenshot" and self.windows is not None:
            return self.windows.screenshot(str(args.get("path", "screenshots/latest.png")))
        if name == "vision_describe" and self.vision is not None:
            path = self._resolve(str(args["path"]))
            return self.vision.describe(path, str(args["prompt"]))

        if name == "mcp_list_servers" and self.mcp is not None:
            return json.dumps(self.mcp.list_servers(), ensure_ascii=False)
        if name == "mcp_list_tools" and self.mcp is not None:
            return json.dumps(self.mcp.list_tools(str(args["server"])), ensure_ascii=False)
        if name == "mcp_call" and self.mcp is not None:
            result = self.mcp.call(str(args["server"]), str(args["tool"]), dict(args["arguments"]))
            return json.dumps(result, ensure_ascii=False)

        raise ToolError(f"Unknown or unavailable tool: {name}")

    def _audit_args(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        clean = dict(args)
        if name == "write_file" and "content" in clean:
            clean["content"] = f"<redacted {len(str(clean['content']))} chars>"
        if name == "windows_type" and "text" in clean:
            clean["text"] = f"<redacted {len(str(clean['text']))} chars>"
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
        if path.stat().st_size > 500_000:
            raise ToolError("File exceeds text read limit (500 KB)")
        return path.read_text(encoding="utf-8")

    def _write_file(self, relative: str, content: str) -> str:
        path = self._resolve(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"Wrote {path.relative_to(self.workspace)} ({len(content)} chars)"

    def _powershell(self, command: str, timeout: int) -> str:
        if os.name != "nt":
            raise ToolError("PowerShell tool is enabled only on Windows")
        completed = subprocess.run(
            ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
            cwd=self.workspace,
            capture_output=True,
            text=True,
            timeout=max(1, min(timeout, 120)),
            shell=False,
        )
        output = ((completed.stdout or "") + (completed.stderr or "")).strip()
        if len(output) > 50_000:
            output = output[-50_000:]
        return f"exit_code={completed.returncode}\n{output}".strip()
