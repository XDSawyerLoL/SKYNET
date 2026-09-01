from __future__ import annotations

import argparse
import json
from pathlib import Path

from .arena import SyntheticAgentArena
from .config import Config
from .fuzz import FastPolicyFuzzer
from .reality import RealityAccelerator, ShadowTrajectoryAnalyzer
from .trajectories import TrajectoryStore


def _paths(root: Path) -> tuple[Config, Path]:
    config = Config.load(root)
    return config, config.data_dir / "reality"


def main() -> None:
    parser = argparse.ArgumentParser(prog="skynet-sim", description="SKYNET accelerated reality and shadow-replay laboratory")
    parser.add_argument("--root", default=".", help="SKYNET project root")
    sub = parser.add_subparsers(dest="command", required=True)

    fuzz = sub.add_parser("fuzz", help="Run very high-speed deterministic Policy/Mandate/Permission mutation fuzzing")
    fuzz.add_argument("--cases", type=int, default=100_000)
    fuzz.add_argument("--seed", type=int, default=8196)
    fuzz.add_argument("--strict", action="store_true")

    core = sub.add_parser("core", help="Run persistence/restart core soak and fault simulation")
    core.add_argument("--episodes", type=int, default=10_000)
    core.add_argument("--workers", type=int, default=8)
    core.add_argument("--seed", type=int, default=8196)
    core.add_argument("--virtual-minutes", type=float, default=60.0,
                      help="Synthetic operational minutes represented by one episode; reporting only")
    core.add_argument("--strict", action="store_true", help="Exit non-zero if any invariant fails")

    agent = sub.add_parser("agent", help="Run the real local model inside an isolated synthetic tool arena")
    agent.add_argument("--episodes", type=int, default=50)
    agent.add_argument("--model", default=None, help="Ollama model; defaults to SKYNET_MODEL")
    agent.add_argument("--seed", type=int, default=8196)
    agent.add_argument("--strict-pass-rate", type=float, default=None,
                       help="Exit non-zero when model arena pass rate is below this threshold")

    shadow = sub.add_parser("shadow", help="Analyze historical trajectories without tools or side effects")
    shadow.add_argument("--limit", type=int, default=1000)

    promote = sub.add_parser("promote-failures", help="Turn latest simulation failures into historical regression seeds")
    promote.add_argument("--limit", type=int, default=500)

    sub.add_parser("report", help="Print latest accelerated reality report")

    args = parser.parse_args()
    root = Path(args.root).resolve()
    config, output = _paths(root)

    if args.command == "fuzz":
        report = FastPolicyFuzzer(output, seed=args.seed).run(args.cases)
        print(json.dumps({
            "cases": report.cases,
            "passed": report.passed,
            "pass_rate": report.pass_rate,
            "permission_checks": report.permission_checks,
            "elapsed_seconds": report.elapsed_seconds,
            "cases_per_second": report.cases_per_second,
            "failures": len(report.failures),
            "report": str(output / "fuzz-latest.json"),
        }, ensure_ascii=False, indent=2))
        if args.strict and report.pass_rate < 1.0:
            raise SystemExit(4)
        return

    if args.command == "core":
        accelerator = RealityAccelerator(output, seed=args.seed)
        report = accelerator.run(
            episodes=args.episodes,
            workers=args.workers,
            virtual_minutes_per_episode=args.virtual_minutes,
        )
        print(json.dumps({
            "run_id": report.run_id,
            "episodes": report.episodes,
            "virtual_hours": report.virtual_hours,
            "operations": report.operations,
            "failed_episodes": report.failed_episodes,
            "pass_rate": report.pass_rate,
            "elapsed_seconds": report.elapsed_seconds,
            "episodes_per_second": report.episodes_per_second,
            "fault_counts": report.fault_counts,
            "failure_counts": report.failure_counts,
            "report": str(output / "latest.json"),
        }, ensure_ascii=False, indent=2))
        if args.strict and report.failed_episodes:
            raise SystemExit(2)
        return

    if args.command == "agent":
        model = args.model or config.model
        report = SyntheticAgentArena(output, config.ollama_url, model, seed=args.seed).run(args.episodes)
        print(json.dumps({
            "model": report["model"],
            "episodes": report["episodes"],
            "passed": report["passed"],
            "pass_rate": report["pass_rate"],
            "mean_score": report["mean_score"],
            "failure_counts": report["failure_counts"],
            "report": str(output / "model-latest.json"),
        }, ensure_ascii=False, indent=2))
        if args.strict_pass_rate is not None and float(report["pass_rate"]) < float(args.strict_pass_rate):
            raise SystemExit(3)
        return

    if args.command == "report":
        path = output / "latest.json"
        if not path.exists():
            raise SystemExit("No reality report yet. Run: skynet-sim core")
        print(path.read_text(encoding="utf-8"))
        return

    trajectories = TrajectoryStore(config.data_dir / "trajectories.db")
    try:
        if args.command == "shadow":
            result = ShadowTrajectoryAnalyzer().analyze(trajectories, limit=args.limit)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        accelerator = RealityAccelerator(output)
        count = accelerator.promote_failures(trajectories, limit=args.limit)
        print(json.dumps({"promoted_failures": count, "source": str(output / "failures.jsonl")}, ensure_ascii=False, indent=2))
    finally:
        trajectories.close()


if __name__ == "__main__":
    main()
