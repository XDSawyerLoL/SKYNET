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
                "version": "0.7",
                "hardware": runtime.profiler.snapshot().as_dict(),
                "lab_backends": [asdict(x) for x in runtime.lab.backends()],
                "sandbox_candidates": [asdict(x) for x in runtime.sandbox.list()],
                "lab_jobs": [asdict(x) for x in runtime.lab.list()[:10]],
                "baseline": asdict(runtime.adaptation.baseline()) if runtime.adaptation.baseline() else None,
                "risk_budget": runtime.risk.budget,
            })
        elif cmd == "hardware":
            _json(runtime.profiler.snapshot().as_dict())
        elif cmd == "telemetry":
            _json(runtime.telemetry.recent(50))
        elif cmd == "redteam":
            model = args[1] if len(args) > 1 else (runtime.router.preferred_model or runtime.config.model)
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
            model = args[1] if len(args) > 1 else (runtime.router.preferred_model or runtime.config.model)
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
        elif cmd == "generate-candidate":
            signature = args[1] if len(args) > 1 else None
            _json(asdict(runtime.candidate_generator.generate(signature)))
        elif cmd == "lab-backends":
            _json([asdict(x) for x in runtime.lab.backends()])
        elif cmd == "lab-list":
            _json([asdict(x) for x in runtime.lab.list()])
        elif cmd == "lab-prepare":
            if len(args) < 2:
                raise SystemExit("usage: skynet-evolve lab-prepare <candidate> [windows-sandbox|wsl2|static-only]")
            backend = args[2] if len(args) > 2 else None
            _json(asdict(runtime.lab.prepare(args[1], backend)))
        elif cmd == "lab-run":
            if len(args) < 2:
                raise SystemExit("usage: skynet-evolve lab-run <job_id>")
            print(runtime.lab.launch(args[1]))
        else:
            raise SystemExit(
                "commands: status, hardware, telemetry, redteam [model], risk-plan <id>, lora-export, "
                "freeze-baseline [model], sandbox-list, sandbox-stage <name> <kind> <file>, "
                "generate-candidate [signature], lab-backends, lab-list, lab-prepare <candidate> [backend], lab-run <job_id>"
            )
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
