from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json
import time
import uuid


@dataclass(slots=True)
class AgentCard:
    name: str
    agent_id: str
    endpoint: str | None = None
    capabilities: list[str] = field(default_factory=list)
    protocols: list[str] = field(default_factory=lambda: ["skynet-local"])
    trust: str = "local"
    metadata: dict = field(default_factory=dict)


@dataclass(slots=True)
class DelegatedTask:
    task_id: str
    source_agent: str
    target_agent: str
    goal: str
    mandate_hash: str
    created_at: float
    status: str = "submitted"

    @classmethod
    def create(cls, source_agent: str, target_agent: str, goal: str, mandate_hash: str) -> "DelegatedTask":
        return cls(uuid.uuid4().hex, source_agent, target_agent, goal, mandate_hash, time.time())


class AgentRegistry:
    """Local registry shaped for future A2A interoperability.

    This is intentionally not advertised as full A2A v1 compliance yet. Agent
    cards and task envelopes are kept protocol-neutral so an A2A HTTP adapter can
    be added without changing SKYNET's internal agent identity or mandate model.
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

    def register(self, card: AgentCard) -> None:
        data = self._load()
        data[card.agent_id] = asdict(card)
        self._save(data)

    def get(self, agent_id: str) -> AgentCard:
        raw = self._load().get(agent_id)
        if raw is None:
            raise KeyError(agent_id)
        return AgentCard(**raw)

    def list(self) -> list[AgentCard]:
        return [AgentCard(**raw) for raw in self._load().values()]

    def find_capability(self, capability: str) -> list[AgentCard]:
        needle = capability.strip().lower()
        return [card for card in self.list() if needle in {x.lower() for x in card.capabilities}]
