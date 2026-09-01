from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .health import GlobalControl
from .policy import ActionDecision, ActionRequest, MandateStore, PolicyEngine, ReceiptStore
from .semantic import SemanticMemory
from .swarm import SwarmEngine
from .tools import ToolBus


class GovernedToolBus:
    """Mandatory policy boundary around all agent tools.

    The language model can propose a tool call, but cannot decide whether the
    mandate permits it. ToolBus permissions remain a second independent
    enforcement layer. The global kill-switch is checked before both.
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
        control: GlobalControl | None = None,
    ) -> None:
        self.inner = inner
        self.mandates = mandates
        self.policy = policy
        self.receipts = receipts
        self.agent_id = agent_id
        self.semantic = semantic
        self.swarm = swarm
        self.control = control

    def schemas(self) -> list[dict[str, Any]]:
        schemas = list(self.inner.schemas())
        if self.swarm is not None:
            schemas.append({
                "type": "function",
                "function": {
                    "name": "swarm_analyze",
                    "description": "Run a bounded hierarchical graph of independent local specialist agents, preserve the trace, then synthesize findings. Read-only compute.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "goal": {"type": "string"},
                            "roles": {"type": "array", "items": {"type": "string"}, "maxItems": 12},
                        },
                        "required": ["goal"],
                    },
                },
            })
        return schemas

    @staticmethod
    def _target(name: str, args: dict[str, Any]) -> str:
        for key in ("path", "server", "title", "target", "tool", "url", "selector", "query"):
            if key in args and args[key] not in (None, ""):
                return str(args[key])[:1000]
        return "local"

    @staticmethod
    def _risk(name: str) -> int:
        observe = {
            "list_files", "read_file", "remember", "list_skills", "read_skill", "windows_list",
            "windows_accessibility", "vision_describe", "mcp_list_servers", "mcp_list_tools", "swarm_analyze",
            "create_plan", "update_plan", "session_list", "session_search", "integration_list",
            "integration_capabilities", "browser_snapshot", "dev_doctor", "dev_tree", "dev_git_status",
            "dev_git_diff", "dev_search",
        }
        moderate = {
            "windows_focus", "windows_type", "windows_invoke", "windows_screenshot", "write_file", "save_skill",
            "browser_back", "browser_click", "browser_type", "browser_screenshot",
        }
        if name in observe:
            return 5
        if name == "browser_navigate":
            return 15
        if name in moderate:
            return 35
        if name == "dev_run_tests":
            return 50
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

        if self.control is not None and self.control.engaged():
            decision = ActionDecision(False, "global_kill_switch", "global SKYNET kill-switch is engaged", mandate.policy_hash)
            self.receipts.append(request, decision, "kill_switch_denied")
            return "DENIED BY GLOBAL KILL SWITCH: explicit user re-arm required"

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
