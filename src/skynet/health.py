from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import os
import re
import subprocess
import sys
import time


_COMPONENT = re.compile(r"^[a-zA-Z0-9_.-]+$")


@dataclass(frozen=True, slots=True)
class Heartbeat:
    component: str
    pid: int
    state: str
    timestamp: float


class HeartbeatStore:
    """Process-safe heartbeat files: one atomic file per component."""

    def __init__(self, path: Path) -> None:
        self.root = path
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, component: str) -> Path:
        if not _COMPONENT.fullmatch(component):
            raise ValueError("invalid heartbeat component")
        return self.root / f"{component}.json"

    def beat(self, component: str, state: str = "ok", pid: int | None = None) -> Heartbeat:
        item = Heartbeat(component, int(pid or os.getpid()), state, time.time())
        target = self._path(component)
        temp = target.with_suffix(f".{os.getpid()}.tmp")
        temp.write_text(json.dumps(asdict(item), ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(target)
        return item

    def get(self, component: str) -> Heartbeat | None:
        target = self._path(component)
        if not target.exists():
            return None
        try:
            return Heartbeat(**json.loads(target.read_text(encoding="utf-8")))
        except Exception:
            return None

    def stale(self, component: str, max_age_s: float) -> bool:
        item = self.get(component)
        return item is None or (time.time() - item.timestamp) > max(1.0, float(max_age_s))


class GlobalControl:
    """Deterministic global stop flag checked below model reasoning."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def engage(self, reason: str = "user-requested") -> None:
        payload = {"engaged": True, "reason": reason[:1000], "timestamp": time.time()}
        temp = self.path.with_suffix(f".{os.getpid()}.tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def release(self) -> None:
        self.path.unlink(missing_ok=True)

    def status(self) -> dict:
        if not self.path.exists():
            return {"engaged": False}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"engaged": True, "reason": "invalid control file"}
        except Exception:
            return {"engaged": True, "reason": "unreadable control file"}

    def engaged(self) -> bool:
        return bool(self.status().get("engaged", False))


class CrashLoopGuard:
    def __init__(self, path: Path, max_crashes: int = 3, window_s: int = 300) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_crashes = max(1, int(max_crashes))
        self.window_s = max(30, int(window_s))

    def _load(self) -> list[float]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return [float(x) for x in data if isinstance(x, (int, float))]
        except Exception:
            return []

    def _save(self, events: list[float]) -> None:
        temp = self.path.with_suffix(f".{os.getpid()}.tmp")
        temp.write_text(json.dumps(events[-20:], indent=2), encoding="utf-8")
        temp.replace(self.path)

    def record_crash(self) -> int:
        now = time.time()
        events = [x for x in self._load() if now - x <= self.window_s]
        events.append(now)
        self._save(events)
        return len(events)

    def count(self) -> int:
        now = time.time()
        original = self._load()
        events = [x for x in original if now - x <= self.window_s]
        if len(events) != len(original):
            self._save(events)
        return len(events)

    def blocked(self) -> bool:
        return self.count() >= self.max_crashes

    def reset(self) -> None:
        self.path.unlink(missing_ok=True)


class WorkerSupervisor:
    """Separate watchdog for the autonomy worker.

    Restarts unexpected worker failures or heartbeat stalls unless the global
    kill-switch is engaged or crash-loop protection trips. It never weakens
    agent permissions.
    """

    def __init__(self, root: Path, data_dir: Path, poll_s: int = 5, stale_after_s: int = 30) -> None:
        self.root = root.resolve()
        self.heartbeat = HeartbeatStore(data_dir / "heartbeats")
        self.control = GlobalControl(data_dir / "kill-switch.json")
        self.crashes = CrashLoopGuard(data_dir / "worker-crashes.json")
        self.poll_s = max(2, int(poll_s))
        self.stale_after_s = max(15, int(stale_after_s))

    def _spawn(self) -> subprocess.Popen:
        env = dict(os.environ)
        env["SKYNET_SUPERVISED"] = "1"
        return subprocess.Popen(
            [sys.executable, "-m", "skynet.worker"],
            cwd=self.root,
            env=env,
            shell=False,
        )

    @staticmethod
    def _stop_child(child: subprocess.Popen) -> None:
        if child.poll() is not None:
            return
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)

    def run(self) -> int:
        child: subprocess.Popen | None = None
        child_started = 0.0
        try:
            while True:
                self.heartbeat.beat("supervisor", "monitoring")
                if self.control.engaged():
                    if child is not None:
                        self._stop_child(child)
                    return 0
                if self.crashes.blocked():
                    self.control.engage("crash-loop protection")
                    if child is not None:
                        self._stop_child(child)
                    return 2
                if child is None:
                    child = self._spawn()
                    child_started = time.time()
                    self.heartbeat.beat("supervisor", f"worker-started:{child.pid}")

                code = child.poll()
                if code is not None:
                    if code == 0:
                        return 0
                    self.crashes.record_crash()
                    child = None
                    time.sleep(min(self.poll_s, 5))
                    continue

                if time.time() - child_started > self.stale_after_s:
                    worker = self.heartbeat.get("worker")
                    wrong_pid = worker is None or worker.pid != child.pid
                    stale = worker is None or (time.time() - worker.timestamp) > self.stale_after_s
                    if wrong_pid or stale:
                        self.heartbeat.beat("supervisor", f"worker-hung:{child.pid}")
                        self._stop_child(child)
                        self.crashes.record_crash()
                        child = None
                        continue

                time.sleep(self.poll_s)
        except KeyboardInterrupt:
            if child is not None:
                self._stop_child(child)
            return 0
