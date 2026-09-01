from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json

from .ollama import OllamaError
from .policy_adapters import AP2ConstraintAdapter, ERC8196Adapter, OAuthScopeAdapter
from .runtime import Runtime


BANNER = """\nSKYNET v0.5 — Measured Evolution
Governed execution • Objective evals • Canary promotion • Rollback • Capability leases
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
    deployed = runtime.deployments.get("reasoning-model")
    print(f"Agent ID:      {runtime.identity.identity.agent_id}")
    print(f"Policy hash:   {mandate.policy_hash[:20]}…")
    print(f"Default model: {config.model}")
    print(f"Model pool:    {', '.join(config.models)}")
    if deployed:
        print(f"Deployment:    {deployed.active} [{deployed.status}] prev={deployed.previous or '-'}")
    else:
        print("Deployment:    <baseline configuration>")
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
    print(":tournament                     Benchmark configured local models objectively")
    print(":scorecards                     Show recent benchmark scorecards")
    print(":learning-proposals             Mine repeated successful trajectories")
    print(":deployments                    Show measured component deployments")
    print(":accept-canary                  Accept current reasoning-model canary")
    print(":rollback-model                 Roll back reasoning-model deployment")
    print(":leases                         Show signed capability leases")
    print(":lease-issue                    Issue a bounded signed capability lease")
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


def _issue_lease(runtime: Runtime) -> None:
    subject = input("Target agent ID: ").strip()
    caps = [x.strip() for x in input("Capabilities (comma separated): ").split(",") if x.strip()]
    try:
        ttl = int(input("TTL seconds (1..86400): ").strip() or "900")
        calls = int(input("Maximum calls: ").strip() or "1")
    except ValueError:
        print("Invalid TTL/call budget.")
        return
    if not subject or not caps:
        print("Target and at least one capability are required.")
        return
    mandate_hash = runtime.mandates.load().policy_hash
    if not _confirm(f"Delegate {caps} to {subject} for {ttl}s / {calls} calls under current mandate?"):
        print("Cancelled.")
        return
    _json(asdict(runtime.leases.issue(subject, caps, mandate_hash, ttl, calls)))


def _run_tournament(runtime: Runtime) -> None:
    print("Running objective local benchmark. No cloud judge is used.")
    scores = runtime.tournament.run(runtime.config.models)
    if not scores:
        print("<no configured models>")
        return
    for score in scores:
        print(f"{score.candidate}: score={score.mean_score:.3f} pass={score.pass_rate:.0%} "
              f"latency={score.latency_median_s:.2f}s safety_failures={score.safety_failures}")
    baseline = next((s for s in scores if s.candidate == runtime.config.model), None)
    candidate = next((s for s in scores if s.candidate != runtime.config.model), None)
    if baseline is None or candidate is None:
        print("Need at least baseline + one alternate configured model for promotion analysis.")
        return
    decision = runtime.tournament.promotion(candidate, baseline)
    print(f"Promotion decision for {candidate.candidate}: {decision.promote} — {decision.reason} (gain={decision.gain:.3f})")
    if decision.promote and _confirm(f"Start {candidate.candidate} as a 20% canary for reasoning-model?"):
        state = runtime.deployments.promote("reasoning-model", candidate.candidate, canary=True,
                                            metadata={"baseline": baseline.candidate, "gain": decision.gain})
        runtime.router.configure_deployment(state.active, state.status)
        print(f"Canary active: {state.active} at 20% deterministic routing.")


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
                _help(); continue
            if text == ":status":
                _status(runtime); continue
            if text == ":tournament":
                try: _run_tournament(runtime)
                except Exception as exc: print(f"Tournament error: {type(exc).__name__}: {exc}")
                continue
            if text == ":scorecards":
                _json(runtime.scores.recent(30)); continue
            if text == ":learning-proposals":
                _json([asdict(p) for p in runtime.trajectory_miner.proposals()]); continue
            if text == ":deployments":
                _json([asdict(x) for x in runtime.deployments.list()]); continue
            if text == ":accept-canary":
                try:
                    state = runtime.deployments.get("reasoning-model")
                    if state is None or state.status != "canary":
                        print("<no reasoning-model canary>")
                    elif _confirm(f"Accept measured canary {state.active} as preferred reasoning model?"):
                        state = runtime.deployments.accept_canary("reasoning-model")
                        runtime.router.configure_deployment(state.active, state.status)
                        print(f"Active preferred model: {state.active}")
                except Exception as exc: print(f"Deployment error: {exc}")
                continue
            if text == ":rollback-model":
                try:
                    state = runtime.deployments.get("reasoning-model")
                    if state is None or not state.previous:
                        print("<no previous reasoning-model deployment>")
                    elif _confirm(f"Roll back from {state.active} to {state.previous}?"):
                        state = runtime.deployments.rollback("reasoning-model", "user-requested rollback")
                        runtime.router.configure_deployment(state.active, state.status)
                        print(f"Rolled back to: {state.active}")
                except Exception as exc: print(f"Deployment error: {exc}")
                continue
            if text == ":leases":
                _json(runtime.leases.list()); continue
            if text == ":lease-issue":
                try: _issue_lease(runtime)
                except Exception as exc: print(f"Lease error: {exc}")
                continue
            if text == ":identity":
                _json(asdict(runtime.identity.identity)); continue
            if text == ":policy":
                mandate = runtime.mandates.load(); _json({**asdict(mandate), "policy_hash": mandate.policy_hash}); continue
            if text == ":policy-erc8196":
                _json(ERC8196Adapter.compile(runtime.mandates.load())); continue
            if text == ":policy-ap2":
                _json(AP2ConstraintAdapter.compile(runtime.mandates.load())); continue
            if text == ":policy-oauth":
                _json(OAuthScopeAdapter.compile(runtime.mandates.load())); continue
            if text == ":receipts":
                items = runtime.receipts.recent(20); _json(items if items else {"receipts": []}); continue
            if text == ":verify-receipts":
                print("VALID" if runtime.receipts.verify_chain() else "INVALID — receipt chain integrity failure"); continue
            if text.startswith(":semantic "):
                query = text.split(maxsplit=1)[1]
                for score, source, content in runtime.semantic.search(query, limit=10):
                    print(f"{score: .3f} | {source} | {content}")
                continue
            if text == ":trajectories":
                _json(runtime.trajectories.recent(20)); continue
            if text == ":agents":
                _json([asdict(card) for card in runtime.agents.list()]); continue
            if text.startswith(":swarm "):
                goal = text.split(maxsplit=1)[1]
                try: print(runtime.swarm.run(goal))
                except Exception as exc: print(f"Swarm error: {exc}")
                continue
            if text == ":memory":
                items = runtime.memory.list_memories(50); print("\n".join(f"- {item}" for item in items) if items else "<no durable memories>"); continue
            if text == ":skills":
                items = runtime.skills.list_skills(); print("\n".join(f"- {item}" for item in items) if items else "<no approved skills>"); continue
            if text == ":skill-candidates":
                items = runtime.skills.list_candidates(); print("\n".join(f"- {item}" for item in items) if items else "<no skill candidates>"); continue
            if text.startswith(":skill-validate "):
                name = text.split(maxsplit=1)[1]
                try:
                    result = runtime.skills.validate_candidate(name); print("VALID" if result.valid else "INVALID")
                    for err in result.errors: print(f"- {err}")
                except Exception as exc: print(f"Skill error: {exc}")
                continue
            if text.startswith(":skill-promote "):
                name = text.split(maxsplit=1)[1]
                try:
                    result = runtime.skills.validate_candidate(name)
                    if not result.valid: print("Cannot promote: " + "; ".join(result.errors))
                    elif _confirm(f"Promote validated skill '{name}' into the active skill library?"): print(runtime.skills.promote(name))
                    else: print("Cancelled.")
                except Exception as exc: print(f"Skill error: {exc}")
                continue
            if text == ":routines":
                items = runtime.routines.list(); print("\n".join(runtime.routines.render(item) for item in items) if items else "<no routines>"); continue
            if text == ":routine-add":
                _add_routine(runtime); continue
            if text == ":routine-run":
                results = runtime.autonomy.run_due()
                if not results: print("<no due routines>")
                for routine, status, reply in results: print(f"[{status}] {routine.name}\n{reply}")
                continue
            if text == ":checkpoints":
                items = runtime.checkpoints.recent(20)
                if not items: print("<no checkpoints>")
                for item in items: print(f"{item.status} | {item.scope}:{item.scope_id} | {item.state}")
                continue
            if text == ":mcp":
                items = runtime.mcp.list_servers(); print("\n".join(f"- {item}" for item in items) if items else "<no MCP servers configured>"); continue
            if text == ":windows":
                try: print(runtime.windows.list_windows())
                except Exception as exc: print(f"Windows error: {exc}")
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
