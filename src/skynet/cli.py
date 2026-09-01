from __future__ import annotations

from pathlib import Path

from .agent import Agent
from .audit import AuditLog
from .config import Config
from .memory import MemoryStore
from .ollama import OllamaClient, OllamaError
from .permissions import PermissionGate
from .skills import SkillStore
from .tools import ToolBus


BANNER = """\nSKYNET v0.1 — Sovereign Local AI\nLocal model • Local memory • Permission-gated tools\nType :help for commands.\n"""


def _confirm(message: str) -> bool:
    print("\n[PERMISSION REQUIRED]")
    print(message)
    answer = input("Allow? [y/N] ").strip().lower()
    return answer in {"y", "yes", "o", "oui"}


def _status(config: Config, client: OllamaClient) -> None:
    print(f"Model:      {config.model}")
    print(f"Ollama:     {config.ollama_url}")
    print(f"Workspace:  {config.workspace}")
    print(f"Data:       {config.data_dir}")
    try:
        models = client.list_models()
        print("Installed:  " + (", ".join(models) if models else "<none>"))
    except OllamaError as exc:
        print(f"Ollama status: ERROR — {exc}")


def main() -> None:
    config = Config.load(Path.cwd())
    memory = MemoryStore(config.data_dir / "memory.db")
    audit = AuditLog(config.data_dir / "audit.jsonl")
    skills = SkillStore(config.data_dir / "skills")
    permissions = PermissionGate()
    client = OllamaClient(config.ollama_url, config.model)
    tools = ToolBus(config.workspace, memory, skills, audit, permissions)
    agent = Agent(client, memory, skills, tools, config.max_tool_rounds)

    print(BANNER)
    _status(config, client)

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
                print(":status  Show runtime status")
                print(":memory  Show durable memories")
                print(":skills  Show installed local skills")
                print(":quit    Exit SKYNET")
                continue
            if text == ":status":
                _status(config, client)
                continue
            if text == ":memory":
                items = memory.list_memories(50)
                print("\n".join(f"- {item}" for item in items) if items else "<no durable memories>")
                continue
            if text == ":skills":
                items = skills.list_skills()
                print("\n".join(f"- {item}" for item in items) if items else "<no skills>")
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
        memory.close()
