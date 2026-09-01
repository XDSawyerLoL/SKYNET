from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import hashlib
import json
import time
import uuid

from .identity import LocalIdentityStore


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(slots=True)
class ValidationCheck:
    name: str
    passed: bool
    evidence: str = ""


@dataclass(slots=True)
class ValidationReport:
    report_id: str
    candidate: str
    created_at: float
    baseline_hash: str
    candidate_hash: str
    checks: list[dict] = field(default_factory=list)
    passed: bool = False
    signer: str = ""
    signature: str = ""


class ValidationReportStore:
    """Tamper-evident local reports signed by SKYNET's sovereign identity."""

    def __init__(self, root: Path, identity: LocalIdentityStore) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.identity = identity

    def create(
        self,
        candidate: str,
        baseline_hash: str,
        candidate_hash: str,
        checks: list[ValidationCheck],
    ) -> ValidationReport:
        payload = {
            "report_id": uuid.uuid4().hex,
            "candidate": candidate,
            "created_at": time.time(),
            "baseline_hash": baseline_hash,
            "candidate_hash": candidate_hash,
            "checks": [asdict(x) for x in checks],
            "passed": bool(checks) and all(x.passed for x in checks),
            "signer": self.identity.identity.agent_id,
        }
        signature = self.identity.sign(hashlib.sha256(_canonical(payload)).digest())
        report = ValidationReport(**payload, signature=signature)
        target = self.root / f"{report.report_id}.json"
        target.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    def verify(self, report: ValidationReport) -> bool:
        payload = asdict(report)
        signature = str(payload.pop("signature", ""))
        expected = hashlib.sha256(_canonical(payload)).digest()
        return self.identity.verify(expected, signature)

    def load(self, report_id: str) -> ValidationReport:
        if not report_id.isalnum():
            raise ValueError("invalid report id")
        data = json.loads((self.root / f"{report_id}.json").read_text(encoding="utf-8"))
        return ValidationReport(**data)

    def recent(self, limit: int = 30) -> list[ValidationReport]:
        items: list[ValidationReport] = []
        paths = sorted(self.root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in paths[: max(1, min(limit, 200))]:
            try:
                items.append(ValidationReport(**json.loads(path.read_text(encoding="utf-8"))))
            except Exception:
                continue
        return items
