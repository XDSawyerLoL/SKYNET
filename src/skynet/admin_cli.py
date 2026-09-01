from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json
import sys
import time

from .runtime import Runtime


def _json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def main() -> None:
    runtime = Runtime.create(Path.cwd(), session_id="admin")
    try:
        args = sys.argv[1:]
        cmd = args[0] if args else "status"
        if cmd == "status":
            _json({
                "version": "0.9",
                "sessions": len(runtime.sessions.list(include_archived=True, limit=500)),
                "integrations": len(runtime.integrations.list()),
                "enabled_integrations": len(runtime.integrations.list(enabled_only=True)),
                "skills": len(runtime.skills.list_skills()),
                "skill_candidates": len(runtime.skills.list_candidates()),
                "automations": len(runtime.routines.list()),
                "channels_recent": len(runtime.channels.recent(100)),
                "swarm_runs": len(runtime.swarm.recent(100)),
                "browser_mode": runtime.browser.state().mode,
                "tool_count": len(runtime.tools.schemas()),
            })
        elif cmd == "doctor":
            print(runtime.developer.doctor())
        elif cmd == "sessions":
            _json([asdict(x) for x in runtime.sessions.list(include_archived=True)])
        elif cmd == "session-search":
            if len(args) < 2:
                raise SystemExit("usage: skynet-admin session-search <query>")
            _json(runtime.sessions.search(" ".join(args[1:])))
        elif cmd == "session-fork":
            if len(args) < 2:
                raise SystemExit("usage: skynet-admin session-fork <session_id> [title]")
            title = " ".join(args[2:]) or None
            _json(asdict(runtime.sessions.fork(args[1], title=title)))
        elif cmd == "integrations":
            _json([asdict(x) for x in runtime.integrations.list()])
        elif cmd == "capabilities":
            _json(runtime.integrations.capability_index())
        elif cmd == "channels":
            _json([asdict(x) for x in runtime.channels.recent(100)])
        elif cmd == "skill-usage":
            _json(runtime.skills.usage(100))
        elif cmd == "swarm-runs":
            _json(runtime.swarm.recent(50))
        elif cmd == "tools":
            _json([schema.get("function", {}).get("name") for schema in runtime.tools.schemas()])
        elif cmd == "automations":
            _json([asdict(x) for x in runtime.routines.list()])
        elif cmd == "automation-once":
            if len(args) < 4:
                raise SystemExit("usage: skynet-admin automation-once <delay_seconds> <session_id> <prompt>")
            delay = max(0, int(args[1]))
            session_id = args[2]
            prompt = " ".join(args[3:])
            item = runtime.routines.create_once("one-shot", prompt, time.time() + delay, session_id=session_id)
            _json(asdict(item))
        else:
            raise SystemExit(
                "commands: status, doctor, sessions, session-search <query>, session-fork <id> [title], "
                "integrations, capabilities, channels, skill-usage, swarm-runs, tools, automations, "
                "automation-once <delay_seconds> <session_id> <prompt>"
            )
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
