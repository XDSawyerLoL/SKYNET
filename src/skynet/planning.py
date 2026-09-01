from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import uuid


_SAFE_ID = re.compile(r"^[a-zA-Z0-9_-]+$")


@dataclass(slots=True)
class PlanStep:
    text: str
    status: str = "pending"
    evidence: str = ""


@dataclass(slots=True)
class Plan:
    id: str
    goal: str
    steps: list[PlanStep] = field(default_factory=list)
    created_at: str = ""


class PlanStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.mkdir(parents=True, exist_ok=True)

    def create(self, goal: str, steps: list[str]) -> Plan:
        clean_steps = [str(x).strip() for x in steps if str(x).strip()]
        if not goal.strip():
            raise ValueError("Plan goal cannot be empty")
        if not clean_steps or len(clean_steps) > 20:
            raise ValueError("Plan must contain between 1 and 20 steps")
        plan = Plan(
            id=uuid.uuid4().hex[:12],
            goal=goal.strip(),
            steps=[PlanStep(text=s) for s in clean_steps],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._write(plan)
        return plan

    def update(self, plan_id: str, step: int, status: str, evidence: str = "") -> Plan:
        plan = self.read(plan_id)
        if status not in {"pending", "running", "done", "failed", "skipped"}:
            raise ValueError("Invalid plan step status")
        if step < 1 or step > len(plan.steps):
            raise IndexError("Plan step is out of range")
        target = plan.steps[step - 1]
        target.status = status
        target.evidence = evidence[:4000]
        self._write(plan)
        return plan

    def read(self, plan_id: str) -> Plan:
        if not _SAFE_ID.fullmatch(plan_id):
            raise ValueError("Invalid plan id")
        path = self.path / f"{plan_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Unknown plan: {plan_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return Plan(
            id=data["id"],
            goal=data["goal"],
            steps=[PlanStep(**item) for item in data["steps"]],
            created_at=data["created_at"],
        )

    def _write(self, plan: Plan) -> None:
        payload = json.dumps(asdict(plan), ensure_ascii=False, indent=2)
        target = self.path / f"{plan.id}.json"
        temp = target.with_suffix(".tmp")
        temp.write_text(payload, encoding="utf-8")
        temp.replace(target)

    @staticmethod
    def render(plan: Plan) -> str:
        lines = [f"Plan {plan.id}: {plan.goal}"]
        for index, step in enumerate(plan.steps, 1):
            extra = f" — {step.evidence}" if step.evidence else ""
            lines.append(f"{index}. [{step.status}] {step.text}{extra}")
        return "\n".join(lines)
