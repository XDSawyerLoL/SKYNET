from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json

from .ollama import OllamaError
from .policy_adapters import AP2ConstraintAdapter, ERC8196Adapter, OAuthScopeAdapter
from .runtime import Runtime


BANNER = """\nSKYNET v0.4 — Sovereign Agent Fabric
Governed execution • Signed receipts • Semantic memory • Parallel swarms • A2A-ready identity
Type :help for commands.
"""


def _confirm(message: str) -> bool:
    print("\n[PERMISSION REQUIRED]")
    print(message)
    answer = input("Allow? [y/N] ").strip().lower()
    return answer in {"y", "yes", "o", "oui"}


def _status(runtime: Runtime) -> None:
    config = runtime.config
    mandate = runtime.mandates.load()
    print(f"Agent ID:      {runtime.identity.identity.agent_id}")
    print(f"Policy hash:   {mandate.policy_hash[:20]}…")
    print(f"Default model: {config.model}")
    print(f"Model pool:    {', '.join(config.models)}")
    print(f"Last route:    {runtime.router.last_route.model} ({runtime.router.last_route.reason})")
    print(f"Vision:        {config.vision_model or '<disabled>'}")
    print(f"Embeddings:    {config.embed_model or '<hashed local fallback>'}")
    print(f"Swarm workers: {config.swarm_workers}")
    print(f"Ollama:        {config.ollama_url}")
    print(f"Workspace:     {config.workspace}")
    print(f"Data:          {config.data_dir}")
    print(f"MCP config:    {config.mcp_config}")
    print(f"Autonomy poll: {config.autonomy_poll_seconds}s")
    servers = runtime.mcp.list_servers()
    print("MCP servers:   " + (", ".join(servers) if servers else "<none>"))
    try:
        models = runtime.router.list_models()
        print("Installed:     " + (", ".join(models) if models else "<none>"))
    except OllamaError as exc:
        print(f"Ollama status: ERROR — {exc}")


def _help() -> None:
    print(":status                         Show runtime status")
    print(":identity                       Show sovereign local identity")
    print(":policy                         Show canonical active mandate")
    print(":policy-erc8196                 Project mandate to ERC-8196 fields")
    print(":policy-ap2                     Project mandate to AP2-style constraints")
    print(":policy-oauth                   Project mandate to delegated OAuth scopes")
    print(":receipts                       Show recent governed action receipts")
    print(":verify-receipts                Verify the signed hash chain")
    print(":semantic <query>               Search semantic local memory")
    print(":trajectories                   Show recent learning trajectories")
    print(":agents                         Show local/interoperable agent cards")
    print(":swarm <goal>                   Run parallel local specialist analysis")
    print(":memory                         Show durable memories")
    print(":skills                         Show approved skills")
    print(":skill-candidates                Show learned skill candidates")
    print(":skill-validate <name>           Validate a candidate")
    print(":skill-promote <name>            Promote a validated candidate")
    print(":routines                        Show local routines")
    print(":routine-add                     Create an interval routine interactively")
    print(":routine-run                     Run routines that are due now")
    print(":checkpoints                     Show recent autonomy checkpoints")
    print(":mcp                             Show configured MCP servers")
    print(":windows                         List visible Windows apps")
    print(":quit                            Exit SKYNET")


def _add_routine(runtime: Runtime) -> None:
    name = input("Routine name: ").strip()
    prompt = input("Instruction: ").strip()
    try:
        minutes = int(input("Interval in minutes (>=1): ").strip())
    except ValueError:
        print("Invalid interval.")
        return
    if minutes < 1:
        print("Invalid interval.")
        return
    if not _confirm(f"Create local routine '{name}' every {minutes} minutes?"):
        print("Cancelled.")
        return
    item = runtime.routines.create(name, prompt, minutes * 60, start_in_seconds=minutes * 60)
    print(runtime.routines.render(item))


def _json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def main() -> None:
    runtime = Runtime.create(Path.cwd(), session_id="cli")
    print(BANNER)
    _status(runtime)

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
                _help()
                continue
            if text == ":status":
                _status(runtime)
                continue
            if text == ":identity":
                _json(asdict(runtime.identity.identity))
                continue
            if text == ":policy":
                mandate = runtime.mandates.load()
                _json({**asdict(mandate), "policy_hash": mandate.policy_hash})
                continue
            if text == ":policy-erc8196":
                _json(ERC8196Adapter.compile(runtime.mandates.load()))
                continue
            if text == ":policy-ap2":
                _json(AP2ConstraintAdapter.compile(runtime.mandates.load()))
                continue
            if text == ":policy-oauth":
                _json(OAuthScopeAdapter.compile(runtime.mandates.load()))
                continue
            if text == ":receipts":
                items = runtime.receipts.recent(20)
                _json(items if items else {"receipts": []})
                continue
            if text == ":verify-receipts":
                print("VALID" if runtime.receipts.verify_chain() else "INVALID — receipt chain integrity failure")
                continue
            if text.startswith(":semantic "):
                query = text.split(maxsplit=1)[1]
                results = runtime.semantic.search(query, limit=10)
                for score, source, content in results:
                    print(f"{score: .3f} | {source} | {content}")
                continue
            if text == ":trajectories":
                _json(runtime.trajectories.recent(20))
                continue
            if text == ":agents":
                _json([asdict(card) for card in runtime.agents.list()])
                continue
            if text.startswith(":swarm "):
                goal = text.split(maxsplit=1)[1]
                try:
                    print(runtime.swarm.run(goal))
                except Exception as exc:
                    print(f"Swarm error: {exc}")
                continue
            if text == ":memory":
                items = runtime.memory.list_memories(50)
                print("\n".join(f"- {item}" for item in items) if items else "<no durable memories>")
                continue
            if text == ":skills":
                items = runtime.skills.list_skills()
                print("\n".join(f"- {item}" for item in items) if items else "<no approved skills>")
                continue
            if text == ":skill-candidates":
                items = runtime.skills.list_candidates()
                print("\n".join(f"- {item}" for item in items) if items else "<no skill candidates>")
                continue
            if text.startswith(":skill-validate "):
                name = text.split(maxsplit=1)[1]
                try:
                    result = runtime.skills.validate_candidate(name)
                    print("VALID" if result.valid else "INVALID")
                    for error in result.errors:
                        print(f"- {error}")
                except Exception as exc:
                    print(f"Skill error: {exc}")
                continue
            if text.startswith(":skill-promote "):
                name = text.split(maxsplit=1)[1]
                try:
                    result = runtime.skills.validate_candidate(name)
                    if not result.valid:
                        print("Cannot promote: " + "; ".join(result.errors))
                    elif _confirm(f"Promote validated skill '{name}' into the active skill library?"):
                        print(runtime.skills.promote(name))
                    else:
                        print("Cancelled.")
                except Exception as exc:
                    print(f"Skill error: {exc}")
                continue
            if text == ":routines":
                items = runtime.routines.list()
                print("\n".join(runtime.routines.render(item) for item in items) if items else "<no routines>")
                continue
            if text == ":routine-add":
                _add_routine(runtime)
                continue
            if text == ":routine-run":
                results = runtime.autonomy.run_due()
                if not results:
                    print("<no due routines>")
                for routine, status, reply in results:
                    print(f"[{status}] {routine.name}\n{reply}")
                continue
            if text == ":checkpoints":
                items = runtime.checkpoints.recent(20)
                if not items:
                    print("<no checkpoints>")
                for item in items:
                    print(f"{item.status} | {item.scope}:{item.scope_id} | {item.state}")
                continue
            if text == ":mcp":
                items = runtime.mcp.list_servers()
                print("\n".join(f"- {item}" for item in items) if items else "<no MCP servers configured>")
                continue
            if text == ":windows":
                try:
                    print(runtime.windows.list_windows())
                except Exception as exc:
                    print(f"Windows error: {exc}")
                continue

            try:
                reply = runtime.agent.ask(text, _confirm)
                print(f"\nSKYNET > {reply}")
                print(f"[model: {runtime.router.last_route.model} | {runtime.router.last_route.reason}]")
            except OllamaError as exc:
                print(f"\nSKYNET ERROR > {exc}")
                print("Check that Ollama is running and at least the default SKYNET_MODEL exists locally.")
            except Exception as exc:
                print(f"\nSKYNET ERROR > {type(exc).__name__}: {exc}")
    finally:
        runtime.close()
