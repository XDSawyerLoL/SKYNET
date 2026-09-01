from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .policy import ActionRequest, MandateStore, PolicyEngine, ReceiptStore
from .semantic import SemanticMemory
from .swarm import SwarmEngine
from .tools import ToolBus


class GovernedToolBus:
    """Mandatory policy boundary around all agent tools.

    The language model can propose a tool call, but cannot decide whether the
    mandate permits it. Existing ToolBus permissions remain a second independent
    enforcement layer.
    """

    def __init__(
        self,
        inner: ToolBus,
        mandates: MandateStore,
        policy: PolicyEngine,
        receipts: ReceiptStore,
        agent_id: str,
        semantic: SemanticMemory | None = None,
        swarm: SwarmEngine | None = None,
    ) -> None:
        self.inner = inner
        self.mandates = mandates
        self.policy = policy
        self.receipts = receipts
        self.agent_id = agent_id
        self.semantic = semantic
        self.swarm = swarm

    def schemas(self) -> list[dict[str, Any]]:
        schemas = list(self.inner.schemas())
        if self.swarm is not None:
            schemas.append({
                "type": "function",
                "function": {
                    "name": "swarm_analyze",
                    "description": "Run several independent local specialist agents in parallel, then synthesize their findings. Read-only compute.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "goal": {"type": "string"},
                            "roles": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
                        },
                        "required": ["goal"],
                    },
                },
            })
        return schemas

    @staticmethod
    def _target(name: str, args: dict[str, Any]) -> str:
        for key in ("path", "server", "title", "target", "tool"):
            if key in args and args[key] not in (None, ""):
                return str(args[key])
        return "local"

    @staticmethod
    def _risk(name: str) -> int:
        if name in {"list_files", "read_file", "remember", "list_skills", "read_skill", "windows_list", "windows_accessibility", "vision_describe", "mcp_list_servers", "mcp_list_tools", "swarm_analyze", "create_plan", "update_plan"}:
            return 5
        if name in {"windows_focus", "windows_type", "windows_invoke", "windows_screenshot", "write_file", "save_skill"}:
            return 35
        if name in {"powershell", "mcp_call"}:
            return 60
        return 75

    @staticmethod
    def _reversible(name: str) -> bool:
        return name not in {"powershell", "mcp_call"}

    def execute(self, name: str, args: dict[str, Any], confirmer: Callable[[str], bool]) -> str:
        mandate = self.mandates.load()
        request = ActionRequest(
            action=name,
            agent_id=self.agent_id,
            target=self._target(name, args),
            value=max(0, int(args.get("value", 0) or 0)),
            risk_score=self._risk(name),
            reversible=self._reversible(name),
            parameters={k: v for k, v in args.items() if k not in {"content", "text", "command"}},
        )
        decision = self.policy.evaluate(mandate, request)
        if not decision.allowed:
            self.receipts.append(request, decision, "policy_denied")
            return f"DENIED BY MANDATE [{decision.code}]: {decision.reason}"

        if name == "swarm_analyze" and self.swarm is not None:
            result = self.swarm.run(str(args["goal"]), list(args.get("roles") or []))
        else:
            result = self.inner.execute(name, args, confirmer)

        status = "ok"
        if result.startswith("DENIED"):
            status = "permission_denied"
        elif result.startswith("TOOL ERROR"):
            status = "error"
        self.receipts.append(request, decision, status)

        if name == "remember" and status == "ok" and self.semantic is not None:
            try:
                self.semantic.add(str(args.get("content", "")), source="durable-memory")
            except Exception:
                pass
        return result
