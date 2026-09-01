from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import json
import re
import time

from .trajectories import TrajectoryStore


_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
]


def scrub_secrets(text: str) -> str:
    clean = text
    for pattern in _SECRET_PATTERNS:
        clean = pattern.sub("[REDACTED]", clean)
    return clean


@dataclass(frozen=True, slots=True)
class BaselineManifest:
    model: str
    created_at: float
    suite_hash: str
    content_hash: str


class AdaptationPipeline:
    """Prepares sovereign local adaptation datasets without training automatically."""

    def __init__(self, root: Path, trajectories: TrajectoryStore) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.trajectories = trajectories

    def export_jsonl(self, name: str = "trajectory-train.jsonl", min_reward: float = 0.75, limit: int = 500) -> Path:
        target = (self.root / name).resolve()
        target.relative_to(self.root)
        rows: list[str] = []
        for item in reversed(self.trajectories.recent(limit)):
            if item.get("outcome") != "success" or float(item.get("reward", 0.0)) < min_reward:
                continue
            prompt = scrub_secrets(str(item.get("goal", "")))
            response = scrub_secrets(str(item.get("evidence", "")))
            rows.append(json.dumps({"messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response},
            ], "metadata": {"trajectory_id": int(item["id"]), "reward": float(item["reward"])}}, ensure_ascii=False))
        target.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
        return target

    def freeze_baseline(self, model: str, suite_hash: str, payload: str) -> BaselineManifest:
        body = payload.encode("utf-8")
        manifest = BaselineManifest(model, time.time(), suite_hash, hashlib.sha256(body).hexdigest())
        path = self.root / "baseline.json"
        if path.exists():
            return BaselineManifest(**json.loads(path.read_text(encoding="utf-8")))
        path.write_text(json.dumps(asdict(manifest), indent=2), encoding="utf-8")
        return manifest

    def baseline(self) -> BaselineManifest | None:
        path = self.root / "baseline.json"
        if not path.exists():
            return None
        return BaselineManifest(**json.loads(path.read_text(encoding="utf-8")))
