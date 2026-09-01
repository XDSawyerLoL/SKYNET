from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import time


@dataclass(slots=True)
class DeploymentState:
    component: str
    active: str
    previous: str | None
    status: str
    promoted_at: float
    scorecard_id: int | None = None
    metadata: dict | None = None


class DeploymentRegistry:
    """Local atomic promotion/rollback state.

    This registry never edits code or downloads models. It records which already
    installed/validated candidate is active for a logical component so a higher
    layer can canary it and roll back deterministically.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")

    def _load(self) -> dict[str, dict]:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}

    def _save(self, data: dict[str, dict]) -> None:
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def get(self, component: str) -> DeploymentState | None:
        raw = self._load().get(component)
        return DeploymentState(**raw) if raw else None

    def promote(self, component: str, candidate: str, scorecard_id: int | None = None, canary: bool = True,
                metadata: dict | None = None) -> DeploymentState:
        data = self._load()
        current = data.get(component)
        previous = current.get("active") if current else None
        if previous == candidate:
            previous = current.get("previous") if current else None
        state = DeploymentState(component, candidate, previous, "canary" if canary else "active", time.time(),
                                scorecard_id, metadata or {})
        data[component] = asdict(state)
        self._save(data)
        return state

    def accept_canary(self, component: str) -> DeploymentState:
        state = self.get(component)
        if state is None:
            raise KeyError(component)
        if state.status != "canary":
            return state
        state.status = "active"
        self._write(state)
        return state

    def rollback(self, component: str, reason: str = "regression") -> DeploymentState:
        state = self.get(component)
        if state is None:
            raise KeyError(component)
        if not state.previous:
            raise RuntimeError("no previous deployment available")
        rolled = DeploymentState(component, state.previous, state.active, "rolled_back", time.time(), None,
                                 {"reason": reason, "from": state.active})
        self._write(rolled)
        return rolled

    def _write(self, state: DeploymentState) -> None:
        data = self._load()
        data[state.component] = asdict(state)
        self._save(data)

    def list(self) -> list[DeploymentState]:
        return [DeploymentState(**raw) for raw in self._load().values()]
