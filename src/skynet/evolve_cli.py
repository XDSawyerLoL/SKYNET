from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json
import sys

from .runtime import Runtime


def _json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def main() -> None:
    runtime = Runtime.create(Path.cwd(), session_id="evolution")
    try:
        args = sys.argv[1:]
        cmd = args[0] if args else "status"
        if cmd == "status":
            _json({
                "version": "0.6",
                "sandbox_candidates": [asdict(x) for x in runtime.sandbox.list()],
                "baseline": asdict(runtime.adaptation.baseline()) if runtime.adaptation.baseline() else None,
                "risk_budget": runtime.risk.budget,
            })
        elif cmd == "redteam":
            model = args[1] if len(args) > 1 else runtime.router.preferred_model
            results = runtime.redteam.run(model)
            _json({"model": model, "passed": all(x.passed for x in results), "cases": [asdict(x) for x in results]})
        elif cmd == "risk-plan":
            if len(args) < 2:
                raise SystemExit("usage: skynet-evolve risk-plan <plan_id>")
            plan = runtime.plans.read(args[1])
            assessment = runtime.risk.assess(plan.goal, [x.text for x in plan.steps])
            _json(asdict(assessment))
        elif cmd == "lora-export":
            path = runtime.adaptation.export_jsonl()
            print(path)
        elif cmd == "freeze-baseline":
            model = args[1] if len(args) > 1 else runtime.router.preferred_model
            scorecards = runtime.scores.recent(50)
            payload = json.dumps(scorecards, sort_keys=True, default=str)
            suite_hash = scorecards[0]["suite_hash"] if scorecards else "no-scorecard-yet"
            _json(asdict(runtime.adaptation.freeze_baseline(model, suite_hash, payload)))
        elif cmd == "sandbox-list":
            _json([asdict(x) for x in runtime.sandbox.list()])
        elif cmd == "sandbox-stage":
            if len(args) < 4:
                raise SystemExit("usage: skynet-evolve sandbox-stage <name> <kind> <file>")
            content = Path(args[3]).read_text(encoding="utf-8")
            _json(asdict(runtime.sandbox.stage(args[1], args[2], content)))
        else:
            raise SystemExit("commands: status, redteam [model], risk-plan <id>, lora-export, freeze-baseline [model], sandbox-list, sandbox-stage <name> <kind> <file>")
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
