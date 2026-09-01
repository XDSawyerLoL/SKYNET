from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import json
import re
import time


_NAME = re.compile(r"^[a-zA-Z0-9_.-]+$")


@dataclass(frozen=True, slots=True)
class CandidateArtifact:
    name: str
    kind: str
    sha256: str
    created_at: float
    status: str


class CandidateSandbox:
    """Stores candidate improvements in an isolated local directory.

    V0.6 never executes candidate core code here. It stages text/config/skill
    artifacts for static inspection, evaluation and later canary promotion.
    """

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def stage(self, name: str, kind: str, content: str) -> CandidateArtifact:
        if not _NAME.fullmatch(name):
            raise ValueError("invalid candidate name")
        target = (self.root / name).resolve()
        target.relative_to(self.root)
        target.mkdir(parents=True, exist_ok=True)
        body = content.encode("utf-8")
        digest = hashlib.sha256(body).hexdigest()
        (target / "candidate.txt").write_bytes(body)
        artifact = CandidateArtifact(name, kind, digest, time.time(), "staged")
        (target / "manifest.json").write_text(json.dumps(asdict(artifact), indent=2), encoding="utf-8")
        return artifact

    def list(self) -> list[CandidateArtifact]:
        items: list[CandidateArtifact] = []
        for manifest in sorted(self.root.glob("*/manifest.json")):
            try:
                items.append(CandidateArtifact(**json.loads(manifest.read_text(encoding="utf-8"))))
            except Exception:
                continue
        return items
