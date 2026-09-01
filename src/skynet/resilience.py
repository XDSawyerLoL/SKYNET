from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import time

from .identity import LocalIdentityStore


@dataclass(frozen=True, slots=True)
class CrashState:
    restart_count: int
    window_seconds: int
    max_restarts: int
    blocked: bool


class KillSwitch:
    """Out-of-band local stop flag checked by workers/supervisors."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def activate(self, reason: str = "user") -> None:
        payload = {"active": True, "reason": reason, "ts": time.time()}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)

    def active(self) -> bool:
        return self.path.exists()

    def status(self) -> dict:
        if not self.path.exists():
            return {"active": False}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"active": True, "reason": "unreadable kill-switch file"}


class CrashLoopGuard:
    """Persistent restart limiter independent from the supervised process."""

    def __init__(self, path: Path, max_restarts: int = 4, window_seconds: int = 300) -> None:
        self.path = path
        self.max_restarts = max(1, max_restarts)
        self.window_seconds = max(30, window_seconds)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[float]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return [float(x) for x in data.get("restarts", [])]
        except Exception:
            return []

    def _save(self, values: list[float]) -> None:
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps({"restarts": values}, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def record_restart(self, now: float | None = None) -> CrashState:
        now = time.time() if now is None else float(now)
        recent = [x for x in self._load() if now - x <= self.window_seconds]
        recent.append(now)
        self._save(recent)
        return CrashState(len(recent), self.window_seconds, self.max_restarts, len(recent) > self.max_restarts)

    def state(self, now: float | None = None) -> CrashState:
        now = time.time() if now is None else float(now)
        recent = [x for x in self._load() if now - x <= self.window_seconds]
        return CrashState(len(recent), self.window_seconds, self.max_restarts, len(recent) > self.max_restarts)

    def reset(self) -> None:
        self.path.unlink(missing_ok=True)


@dataclass(frozen=True, slots=True)
class ValidationReport:
    report_id: str
    created_at: float
    subject: str
    verdict: str
    checks: dict
    signature: str


class ValidationReportStore:
    """Signed local reports for candidate/health validation evidence."""

    def __init__(self, root: Path, identity: LocalIdentityStore) -> None:
        self.root = root
        self.identity = identity
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, subject: str, verdict: str, checks: dict) -> ValidationReport:
        created = time.time()
        body = json.dumps({"created_at": created, "subject": subject, "verdict": verdict, "checks": checks}, sort_keys=True, ensure_ascii=False).encode("utf-8")
        report_id = self.identity.sign(body)[:24]
        signature = self.identity.sign(report_id.encode("ascii") + body)
        report = ValidationReport(report_id, created, subject, verdict, checks, signature)
        path = self.root / f"{report_id}.json"
        path.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    def verify(self, report: ValidationReport) -> bool:
        body = json.dumps({"created_at": report.created_at, "subject": report.subject, "verdict": report.verdict, "checks": report.checks}, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return self.identity.verify(report.report_id.encode("ascii") + body, report.signature)

    def list(self, limit: int = 30) -> list[ValidationReport]:
        out: list[ValidationReport] = []
        for path in sorted(self.root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:max(1, limit)]:
            try:
                out.append(ValidationReport(**json.loads(path.read_text(encoding="utf-8"))))
            except Exception:
                continue
        return out
