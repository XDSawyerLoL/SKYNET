from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json
import sys

from .backup import BackupManager
from .config import Config
from .health import GlobalControl
from .runtime import Runtime
from .trust import ValidationCheck


def _json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _candidate(runtime: Runtime, name: str):
    return next((x for x in runtime.sandbox.list() if x.name == name), None)


def _restore_without_runtime(args: list[str], cmd: str) -> None:
    if len(args) < 2:
        usage = "restore-portable <archive.zip>" if cmd == "restore-portable" else "restore-protected <archive.dpapi>"
        raise SystemExit(f"usage: skynet-trust {usage} [--overwrite]")
    root = Path.cwd().resolve()
    config = Config.load(root)
    control = GlobalControl(config.data_dir / "kill-switch.json")
    if not control.engaged():
        raise SystemExit("restore refused: engage the global kill-switch first, then close SKYNET Desktop before restoring")
    manager = BackupManager(config.data_dir, config.data_dir / "backups")
    overwrite = "--overwrite" in args[2:]
    if cmd == "restore-portable":
        restored = manager.import_portable(Path(args[1]), overwrite=overwrite)
    else:
        restored = manager.import_windows_protected(Path(args[1]), overwrite=overwrite)
    print(f"restored_files={restored}")
    print("Restore complete. Review state before explicitly rearming SKYNET.")


def main() -> None:
    args = sys.argv[1:]
    cmd = args[0] if args else "status"

    if cmd in {"restore-portable", "restore-protected"}:
        _restore_without_runtime(args, cmd)
        return

    runtime = Runtime.create(Path.cwd(), session_id="trust")
    try:
        if cmd == "status":
            worker = runtime.heartbeats.get("worker")
            supervisor = runtime.heartbeats.get("supervisor")
            _json({
                "version": "0.8",
                "kill_switch": runtime.control.status(),
                "worker_heartbeat": asdict(worker) if worker else None,
                "supervisor_heartbeat": asdict(supervisor) if supervisor else None,
                "validation_reports": len(runtime.reports.recent(100)),
                "historical_failure_regressions": len(runtime.regression.build(100)),
            })
            return

        if cmd == "kill":
            reason = " ".join(args[1:]).strip() or "user-requested emergency stop"
            runtime.control.engage(reason)
            print("GLOBAL KILL SWITCH ENGAGED")
            return

        if cmd == "rearm":
            runtime.control.release()
            print("GLOBAL KILL SWITCH RELEASED BY EXPLICIT USER COMMAND")
            return

        if cmd == "regression":
            model = args[1] if len(args) > 1 else (runtime.router.preferred_model or runtime.config.model)
            results = runtime.regression.run(model)
            _json({"model": model, "passed": all(x.passed for x in results), "cases": [asdict(x) for x in results]})
            return

        if cmd == "reports":
            _json([{**asdict(x), "verified": runtime.reports.verify(x)} for x in runtime.reports.recent(30)])
            return

        if cmd == "verify-report":
            if len(args) < 2:
                raise SystemExit("usage: skynet-trust verify-report <report_id>")
            report = runtime.reports.load(args[1])
            _json({"report": asdict(report), "verified": runtime.reports.verify(report)})
            return

        if cmd == "validate-candidate":
            if len(args) < 2:
                raise SystemExit("usage: skynet-trust validate-candidate <candidate_name>")
            artifact = _candidate(runtime, args[1])
            if artifact is None:
                raise SystemExit(f"unknown staged candidate: {args[1]}")
            baseline = runtime.adaptation.baseline()
            model = runtime.router.preferred_model or runtime.config.model
            red = runtime.redteam.run(model)
            regressions = runtime.regression.run(model)
            score = runtime.scores.latest_for(model)
            checks = [
                ValidationCheck("candidate-staged", True, f"sha256={artifact.sha256}; kind={artifact.kind}"),
                ValidationCheck("immutable-baseline-present", baseline is not None, str(asdict(baseline)) if baseline else "baseline missing"),
                ValidationCheck("current-model-red-team", all(x.passed for x in red), f"passed={sum(1 for x in red if x.passed)}/{len(red)}"),
                ValidationCheck("historical-regressions", all(x.passed for x in regressions), f"passed={sum(1 for x in regressions if x.passed)}/{len(regressions)}"),
                ValidationCheck("objective-scorecard", score is not None and int(score.get("safety_failures", 1)) == 0, str(score or "scorecard missing")),
            ]
            report = runtime.reports.create(
                artifact.name,
                baseline.content_hash if baseline else "missing",
                artifact.sha256,
                checks,
            )
            _json({"report": asdict(report), "verified": runtime.reports.verify(report)})
            return

        if cmd == "backup-portable":
            _json(asdict(runtime.backups.export_portable()))
            return

        if cmd == "backup-protected":
            _json(asdict(runtime.backups.export_windows_protected()))
            return

        raise SystemExit(
            "commands: status, kill [reason], rearm, regression [model], reports, verify-report <id>, "
            "validate-candidate <name>, backup-portable, backup-protected, restore-portable <zip> [--overwrite], "
            "restore-protected <dpapi> [--overwrite]"
        )
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
