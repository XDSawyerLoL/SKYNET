from __future__ import annotations

from collections.abc import Callable
import time

from .agent import Agent
from .checkpoints import CheckpointStore
from .scheduler import Routine, RoutineStore


class AutonomyRunner:
    """Runs due local routines without ever auto-approving consequential actions."""

    def __init__(self, routines: RoutineStore, checkpoints: CheckpointStore, agent: Agent) -> None:
        self.routines = routines
        self.checkpoints = checkpoints
        self.agent = agent

    def run_one(self, routine: Routine) -> tuple[str, str]:
        previous = self.checkpoints.latest("routine", routine.id)
        resume_note = ""
        if previous and previous.status in {"running", "failed", "needs_user"}:
            resume_note = (
                "\nA previous checkpoint exists. Use it only as context and verify current state before acting:\n"
                + str(previous.state)
            )
        self.checkpoints.save(
            "routine", routine.id, "running",
            {"name": routine.name, "prompt": routine.prompt, "started_at": time.time()},
        )
        prompt = (
            f"[AUTONOMOUS ROUTINE: {routine.name}]\n{routine.prompt}\n"
            "Run locally. Read-only and SAFE tools may proceed. Any action requiring confirmation will be denied in unattended mode; "
            "if that happens, explain exactly what user approval is needed. Verify results before declaring success."
            + resume_note
        )
        denied = False

        def deny_sensitive(_: str) -> bool:
            nonlocal denied
            denied = True
            return False

        try:
            reply = self.agent.ask(prompt, deny_sensitive)
            status = "needs_user" if denied else "ok"
            self.checkpoints.save("routine", routine.id, status, {"reply": reply, "finished_at": time.time()})
            self.routines.mark_result(routine.id, status)
            return status, reply
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            self.checkpoints.save("routine", routine.id, "failed", {"error": message, "failed_at": time.time()})
            self.routines.mark_result(routine.id, "failed")
            return "failed", message

    def run_due(self, notify: Callable[[Routine, str, str], None] | None = None) -> list[tuple[Routine, str, str]]:
        results: list[tuple[Routine, str, str]] = []
        for routine in self.routines.due():
            status, reply = self.run_one(routine)
            results.append((routine, status, reply))
            if notify is not None:
                notify(routine, status, reply)
        return results
