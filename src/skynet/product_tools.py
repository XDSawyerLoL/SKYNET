from __future__ import annotations

import json
import re
from typing import Any

from .browser import BrowserHarness
from .devtools import DeveloperTools
from .integrations import IntegrationRegistry
from .sessions import SessionStore
from .tools import ToolBus


_TOOL_SAFE = re.compile(r"[^a-zA-Z0-9_]" )


class ProductToolBus(ToolBus):
    """V0.9 product tools layered on the existing governed tool contract."""

    def __init__(self, *args, browser: BrowserHarness | None = None, developer: DeveloperTools | None = None,
                 sessions: SessionStore | None = None, integrations: IntegrationRegistry | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.browser = browser
        self.developer = developer
        self.sessions = sessions
        self.integrations = integrations
        self._dynamic_mcp: dict[str, tuple[str, str]] = {}
        self._mcp_schema_cache: list[dict[str, Any]] | None = None

    @staticmethod
    def _safe_tool_part(value: str) -> str:
        clean = _TOOL_SAFE.sub("_", value.strip())
        return clean[:80] or "tool"

    def _dynamic_mcp_schemas(self) -> list[dict[str, Any]]:
        if self.mcp is None:
            return []
        if self._mcp_schema_cache is not None:
            return list(self._mcp_schema_cache)
        output: list[dict[str, Any]] = []
        mapping: dict[str, tuple[str, str]] = {}
        for server in self.mcp.list_servers():
            try:
                tools = self.mcp.list_tools(server)
            except Exception:
                continue
            for raw in tools[:200]:
                if not isinstance(raw, dict) or not isinstance(raw.get("name"), str):
                    continue
                remote_name = str(raw["name"])
                local_name = f"mcp__{self._safe_tool_part(server)}__{self._safe_tool_part(remote_name)}"[:120]
                if local_name in mapping:
                    continue
                schema = raw.get("inputSchema") if isinstance(raw.get("inputSchema"), dict) else {"type": "object", "properties": {}}
                output.append(self._schema(
                    local_name,
                    f"MCP {server}::{remote_name} — {str(raw.get('description', '')).strip()[:1000]}",
                    schema,
                ))
                mapping[local_name] = (server, remote_name)
        self._dynamic_mcp = mapping
        self._mcp_schema_cache = output
        return list(output)

    def refresh_integrations(self) -> None:
        self._mcp_schema_cache = None
        self._dynamic_mcp.clear()
        if self.integrations is not None and self.mcp is not None:
            self.integrations.discover_mcp(self.mcp.list_servers())

    def schemas(self) -> list[dict[str, Any]]:
        schemas = super().schemas()
        if self.sessions is not None:
            schemas += [
                self._schema("session_list", "List recent SKYNET conversation sessions and projects.", {
                    "type": "object", "properties": {"include_archived": {"type": "boolean"}}
                }),
                self._schema("session_search", "Search exact text fragments across local conversation history.", {
                    "type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]
                }),
            ]
        if self.integrations is not None:
            schemas += [
                self._schema("integration_list", "List configured/discovered integrations and their capabilities.", {
                    "type": "object", "properties": {"enabled_only": {"type": "boolean"}}
                }),
                self._schema("integration_capabilities", "Show the enabled integration capability index.", {
                    "type": "object", "properties": {}
                }),
            ]
        if self.browser is not None:
            schemas += [
                self._schema("browser_navigate", "Navigate the local browser to an absolute http/https URL.", {
                    "type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]
                }),
                self._schema("browser_snapshot", "Read the current browser page text and links. Read-only.", {
                    "type": "object", "properties": {"max_chars": {"type": "integer", "minimum": 1000, "maximum": 50000}}
                }),
                self._schema("browser_back", "Navigate the interactive local browser back. Requires confirmation.", {
                    "type": "object", "properties": {}
                }),
                self._schema("browser_click", "Click a CSS selector in the interactive local browser. Requires confirmation.", {
                    "type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]
                }),
                self._schema("browser_type", "Fill a CSS selector in the interactive local browser. Requires confirmation.", {
                    "type": "object", "properties": {
                        "selector": {"type": "string"}, "text": {"type": "string"}, "submit": {"type": "boolean"}
                    }, "required": ["selector", "text"]
                }),
                self._schema("browser_screenshot", "Capture the current interactive browser page into the workspace. Requires confirmation.", {
                    "type": "object", "properties": {"path": {"type": "string"}}
                }),
            ]
        if self.developer is not None:
            schemas += [
                self._schema("dev_doctor", "Inspect local developer prerequisites without changing anything.", {"type": "object", "properties": {}}),
                self._schema("dev_tree", "List project files while skipping generated/vendor directories.", {
                    "type": "object", "properties": {"max_files": {"type": "integer", "minimum": 1, "maximum": 3000}}
                }),
                self._schema("dev_git_status", "Read git status. Read-only.", {"type": "object", "properties": {}}),
                self._schema("dev_git_diff", "Read git diff. Read-only.", {
                    "type": "object", "properties": {"staged": {"type": "boolean"}}
                }),
                self._schema("dev_search", "Search text across project source files. Read-only.", {
                    "type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]
                }),
                self._schema("dev_run_tests", "Run the repository unit test suite. Executes local project code and requires confirmation.", {
                    "type": "object", "properties": {"timeout": {"type": "integer", "minimum": 10, "maximum": 900}}
                }),
            ]
        schemas += self._dynamic_mcp_schemas()
        return schemas

    def _summary(self, name: str, args: dict[str, Any]) -> str:
        if name.startswith("mcp__"):
            remote = self._dynamic_mcp.get(name)
            return f"Allow dynamic MCP tool {remote[0]}::{remote[1]}?" if remote else f"Allow MCP tool {name}?"
        if name == "browser_back":
            return "Allow SKYNET to navigate the local browser back?"
        if name == "browser_click":
            return f"Allow browser click on selector: {args.get('selector', '?')}"
        if name == "browser_type":
            return f"Allow SKYNET to fill {len(str(args.get('text', '')))} characters into browser selector {args.get('selector', '?')}?"
        if name == "browser_screenshot":
            return f"Allow browser screenshot to {args.get('path', 'screenshots/browser.png')}?"
        if name == "dev_run_tests":
            return "Allow SKYNET to execute this project's unit tests locally?"
        return super()._summary(name, args)

    def _dispatch(self, name: str, args: dict[str, Any]) -> str:
        if name.startswith("mcp__") and self.mcp is not None:
            if not self._dynamic_mcp:
                self._dynamic_mcp_schemas()
            remote = self._dynamic_mcp.get(name)
            if remote is None:
                raise KeyError(f"Unknown dynamic MCP tool: {name}")
            result = self.mcp.call(remote[0], remote[1], args)
            return json.dumps(result, ensure_ascii=False)
        if name == "session_list" and self.sessions is not None:
            return json.dumps([{
                "session_id": item.session_id, "title": item.title, "project": item.project,
                "channel": item.channel, "created_at": item.created_at, "updated_at": item.updated_at,
                "archived": item.archived,
            } for item in self.sessions.list(bool(args.get("include_archived", False)))], ensure_ascii=False)
        if name == "session_search" and self.sessions is not None:
            return json.dumps(self.sessions.search(str(args["query"])), ensure_ascii=False)
        if name == "integration_list" and self.integrations is not None:
            return json.dumps([{
                "name": item.name, "kind": item.kind, "enabled": item.enabled,
                "capabilities": item.capabilities, "trust": item.trust, "source": item.source,
            } for item in self.integrations.list(bool(args.get("enabled_only", False)))], ensure_ascii=False)
        if name == "integration_capabilities" and self.integrations is not None:
            return json.dumps(self.integrations.capability_index(), ensure_ascii=False)

        if name == "browser_navigate" and self.browser is not None:
            return self.browser.navigate(str(args["url"]))
        if name == "browser_snapshot" and self.browser is not None:
            return self.browser.snapshot(int(args.get("max_chars", 40000)))
        if name == "browser_back" and self.browser is not None:
            return self.browser.back()
        if name == "browser_click" and self.browser is not None:
            return self.browser.click(str(args["selector"]))
        if name == "browser_type" and self.browser is not None:
            return self.browser.type_text(str(args["selector"]), str(args["text"]), bool(args.get("submit", False)))
        if name == "browser_screenshot" and self.browser is not None:
            return self.browser.screenshot(str(args.get("path", "screenshots/browser.png")))

        if name == "dev_doctor" and self.developer is not None:
            return self.developer.doctor()
        if name == "dev_tree" and self.developer is not None:
            return self.developer.project_tree(int(args.get("max_files", 500)))
        if name == "dev_git_status" and self.developer is not None:
            return self.developer.git_status()
        if name == "dev_git_diff" and self.developer is not None:
            return self.developer.git_diff(bool(args.get("staged", False)))
        if name == "dev_search" and self.developer is not None:
            return self.developer.search_code(str(args["query"]))
        if name == "dev_run_tests" and self.developer is not None:
            return self.developer.run_tests(int(args.get("timeout", 180)))
        return super()._dispatch(name, args)

    def _audit_args(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        clean = super()._audit_args(name, args)
        if name == "browser_type" and "text" in clean:
            clean["text"] = f"<redacted {len(str(args.get('text', '')))} chars>"
        return clean
