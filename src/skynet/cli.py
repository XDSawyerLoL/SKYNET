from __future__ import annotations

from pathlib import Path

from .agent import Agent
from .audit import AuditLog
from .config import Config
from .mcp import MCPHub
from .memory import MemoryStore
from .ollama import OllamaClient, OllamaError
from .permissions import PermissionGate
from .planning import PlanStore
from .skills import SkillStore
from .tools import ToolBus
from .vision import OllamaVisionClient
from .windows import WindowsController


BANNER = """\nSKYNET v0.2 — Sovereign Local AI
Local model • Persistent memory • Windows control • MCP • Learned skills
Type :help for commands.
"""


def _confirm(message: str) -> bool:
    print("\n[PERMISSION REQUIRED]")
    print(message)
    answer = input("Allow? [y/N] ").strip().lower()
    return answer in {"y", "yes", "o", "oui"}


def _status(config: Config, client: OllamaClient, mcp: MCPHub) -> None:
    print(f"Model:        {config.model}")
    print(f"Vision:       {config.vision_model or '<disabled>'}")
    print(f"Ollama:       {config.ollama_url}")
    print(f"Workspace:    {config.workspace}")
    print(f"Data:         {config.data_dir}")
    print(f"MCP config:   {config.mcp_config}")
    print("MCP servers:  " + (", ".join(mcp.list_servers()) if mcp.list_servers() else "<none>"))
    try:
        models = client.list_models()
        print("Installed:    " + (", ".join(models) if models else "<none>"))
    except OllamaError as exc:
        print(f"Ollama status: ERROR — {exc}")


def main() -> None:
    config = Config.load(Path.cwd())
    memory = MemoryStore(config.data_dir / "memory.db")
    audit = AuditLog(config.data_dir / "audit.jsonl")
    skills = SkillStore(config.data_dir / "skills")
    plans = PlanStore(config.data_dir / "plans")
    permissions = PermissionGate()
    client = OllamaClient(config.ollama_url, config.model)
    vision = OllamaVisionClient(config.ollama_url, config.vision_model)
    windows = WindowsController(config.workspace)
    mcp = MCPHub(config.mcp_config)
    tools = ToolBus(
        config.workspace,
        memory,
        skills,
        audit,
        permissions,
        plans=plans,
        windows=windows,
        mcp=mcp,
        vision=vision,
    )
    agent = Agent(client, memory, skills, tools, config.max_tool_rounds)

    print(BANNER)
    _status(config, client, mcp)

    try:
        while True:
            try:
                text = input("\nYou > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye.")
                break
            if not text:
                continue
            if text in {":quit", ":exit", "/quit", "/exit"}:
                break
            if text == ":help":
                print(":status   Show runtime status")
                print(":memory   Show durable memories")
                print(":skills   Show learned skills")
                print(":mcp      Show configured MCP servers")
                print(":windows  List visible Windows apps")
                print(":quit     Exit SKYNET")
                continue
            if text == ":status":
                _status(config, client, mcp)
                continue
            if text == ":memory":
                items = memory.list_memories(50)
                print("\n".join(f"- {item}" for item in items) if items else "<no durable memories>")
                continue
            if text == ":skills":
                items = skills.list_skills()
                print("\n".join(f"- {item}" for item in items) if items else "<no skills>")
                continue
            if text == ":mcp":
                items = mcp.list_servers()
                print("\n".join(f"- {item}" for item in items) if items else "<no MCP servers configured>")
                continue
            if text == ":windows":
                try:
                    print(windows.list_windows())
                except Exception as exc:
                    print(f"Windows error: {exc}")
                continue

            try:
                reply = agent.ask(text, _confirm)
                print(f"\nSKYNET > {reply}")
            except OllamaError as exc:
                print(f"\nSKYNET ERROR > {exc}")
                print("Check that Ollama is running and SKYNET_MODEL exists locally.")
            except Exception as exc:
                print(f"\nSKYNET ERROR > {type(exc).__name__}: {exc}")
    finally:
        mcp.close()
        memory.close()
