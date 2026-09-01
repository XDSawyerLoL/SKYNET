from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
import json
import random
import tempfile
import time

from .audit import AuditLog
from .channels import ChannelHub
from .identity import LocalIdentityStore
from .memory import MemoryStore
from .permissions import PermissionGate
from .policy import ActionRequest, Mandate, PolicyEngine, ReceiptStore
from .scheduler import RoutineStore
from .sessions import SessionStore
from .trajectories import TrajectoryStore


FAULT_CLASSES = (
    "duplicate_delivery",
    "permission_pressure",
    "replay_attack",
    "risk_overflow",
    "expired_mandate",
    "session_handoff",
    "crash_restart",
    "unknown_tool_injection",
)


@dataclass(frozen=True, slots=True)
class InvariantFailure:
    episode: int
    fault: str
    invariant: str
    detail: str


@dataclass(frozen=True, slots=True)
class SimulationReport:
    run_id: str
    seed: int
    episodes: int
    virtual_hours: float
    operations: int
    failed_episodes: int
    pass_rate: float
    elapsed_seconds: float
    episodes_per_second: float
    fault_counts: dict[str, int]
    failure_counts: dict[str, int]
    failures: list[dict]


class _WorkerHarness:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.identity = LocalIdentityStore(root / "identity.key")
        self.permissions = PermissionGate()
        self.audit = AuditLog(root / "audit.jsonl")
        self._open()

    def _open(self) -> None:
        self.memory = MemoryStore(self.root / "memory.db")
        self.sessions = SessionStore(self.root / "memory.db")
        self.channels = ChannelHub(self.root / "channels.db")
        self.routines = RoutineStore(self.root / "routines.db")
        self.receipts = ReceiptStore(self.root / "receipts.db", self.identity)
        self.policy = PolicyEngine(self.receipts)

    def restart(self) -> None:
        self.close_storage()
        self._open()

    def close_storage(self) -> None:
        self.routines.close()
        self.channels.close()
        self.sessions.close()
        self.memory.close()
        self.receipts.close()

    def close(self) -> None:
        self.close_storage()


class RealityAccelerator:
    """High-speed, no-cloud operational simulation for SKYNET core invariants.

    One episode represents a synthetic period of agent operation, not literal
    wall-clock experience. The accelerator exercises real persistence/policy
    components with deterministic fault injection and converts any invariant
    break into a machine-readable regression seed.
    """

    def __init__(self, output_dir: Path, seed: int = 8196) -> None:
        self.output_dir = output_dir.resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.seed = int(seed)

    @staticmethod
    def _mandate(agent_id: str, now: float) -> Mandate:
        return Mandate(
            mandate_id="reality-default",
            principal="simulated-owner",
            agent_id=agent_id,
            allowed_actions=["*"],
            allowed_targets=["*"],
            valid_after=now - 60,
            valid_until=now + 3600,
            max_risk_score=50,
        )

    @staticmethod
    def _failure(episode: int, fault: str, invariant: str, detail: str) -> InvariantFailure:
        return InvariantFailure(episode, fault, invariant, detail[:1000])

    def _episode(self, harness: _WorkerHarness, episode: int, rng: random.Random) -> tuple[list[InvariantFailure], int, str]:
        failures: list[InvariantFailure] = []
        operations = 0
        fault = FAULT_CLASSES[episode % len(FAULT_CLASSES)]
        sid = f"sim-{episode:08d}"
        token = f"needle-{self.seed}-{episode}"

        try:
            harness.sessions.ensure(sid, title=f"Synthetic session {episode}", project="Reality Accelerator")
            harness.memory.add_message(sid, "user", f"synthetic request {token}")
            harness.memory.add_message(sid, "assistant", "synthetic evidence recorded")
            operations += 3
            hits = harness.sessions.search(token, limit=5)
            operations += 1
            if not hits or hits[0].get("session_id") != sid:
                failures.append(self._failure(episode, fault, "session_search", "session history could not be recovered"))

            event_id = f"evt-{episode}"
            first = harness.channels.receive("synthetic", "peer", "hello", sid, dedupe_key=event_id)
            second = harness.channels.receive("synthetic", "peer", "hello", sid, dedupe_key=event_id)
            operations += 2
            if first.message_id != second.message_id:
                failures.append(self._failure(episode, fault, "channel_idempotency", "duplicate inbound event created two messages"))
            harness.channels.mark(first.message_id, "processed")
            reply1 = harness.channels.send("synthetic", "peer", "reply", sid, dedupe_key=f"reply:{event_id}")
            reply2 = harness.channels.send("synthetic", "peer", "reply", sid, dedupe_key=f"reply:{event_id}")
            operations += 3
            if reply1.message_id != reply2.message_id:
                failures.append(self._failure(episode, fault, "outbox_idempotency", "duplicate outbound event created two messages"))

            if not harness.permissions.authorize("read_file", "read", lambda _msg: False):
                failures.append(self._failure(episode, fault, "observe_permission", "read-only action unexpectedly required approval"))
            if harness.permissions.authorize("write_file", "write", lambda _msg: False):
                failures.append(self._failure(episode, fault, "confirmation_boundary", "sensitive action bypassed denied approval"))
            if harness.permissions.authorize("totally_unknown_tool", "unknown", lambda _msg: True):
                failures.append(self._failure(episode, fault, "unknown_tool_default_deny", "unknown tool was authorized"))
            operations += 3

            now = time.time()
            mandate = self._mandate(harness.identity.identity.agent_id, now)
            nonce = f"replay-{episode}-{rng.randrange(1_000_000)}"
            request = ActionRequest(
                action="read_file", agent_id=mandate.agent_id, target="workspace",
                risk_score=5, nonce=nonce, timestamp=now,
            )
            decision = harness.policy.evaluate(mandate, request)
            operations += 1
            if not decision.allowed:
                failures.append(self._failure(episode, fault, "valid_policy", f"safe request denied: {decision.code}"))
            else:
                harness.receipts.append(request, decision, "ok")
                replay = harness.policy.evaluate(mandate, request)
                operations += 2
                if replay.allowed or replay.code != "replay":
                    failures.append(self._failure(episode, fault, "replay_protection", f"replay result={replay.code}"))

            risky = ActionRequest(
                action="powershell", agent_id=mandate.agent_id, target="local",
                risk_score=90, nonce=f"risk-{episode}", timestamp=now,
            )
            risk_decision = harness.policy.evaluate(mandate, risky)
            operations += 1
            if risk_decision.allowed or risk_decision.code != "risk_limit":
                failures.append(self._failure(episode, fault, "risk_budget", f"high-risk request result={risk_decision.code}"))

            expired = Mandate(
                mandate_id="expired", principal="simulated-owner", agent_id=mandate.agent_id,
                allowed_actions=["*"], allowed_targets=["*"], valid_after=now - 100,
                valid_until=now - 10, max_risk_score=100,
            )
            expired_decision = harness.policy.evaluate(
                expired,
                ActionRequest(action="read_file", agent_id=mandate.agent_id, nonce=f"expired-{episode}", timestamp=now),
            )
            operations += 1
            if expired_decision.allowed or expired_decision.code != "expired":
                failures.append(self._failure(episode, fault, "mandate_expiry", f"expired mandate result={expired_decision.code}"))

            routine = harness.routines.create_once(
                f"once-{episode}", "synthetic check", now + 1, session_id=sid,
            )
            harness.routines.mark_result(routine.id, "ok", now=routine.next_run)
            current = harness.routines.get(routine.id)
            operations += 3
            if current is None or current.enabled or current.run_count != 1:
                failures.append(self._failure(episode, fault, "one_shot_automation", "one-shot routine did not disable exactly once"))

            if fault == "session_handoff":
                fork = harness.sessions.fork(sid, title=f"Fork {episode}", copy_last=10)
                copied = harness.memory.recent_messages(fork.session_id, 10)
                operations += 2
                if len(copied) != 2:
                    failures.append(self._failure(episode, fault, "session_fork", f"expected 2 messages, got {len(copied)}"))

            harness.audit.record("reality_episode", {"episode": episode, "fault": fault}, "ok" if not failures else "failed")
            operations += 1

            if fault == "crash_restart":
                harness.restart()
                operations += 1
                recovered = harness.memory.recent_messages(sid, 10)
                if len(recovered) != 2:
                    failures.append(self._failure(episode, fault, "crash_recovery", f"expected 2 recovered messages, got {len(recovered)}"))
                duplicate_after_restart = harness.channels.receive("synthetic", "peer", "hello", sid, dedupe_key=event_id)
                operations += 2
                if duplicate_after_restart.message_id != first.message_id:
                    failures.append(self._failure(episode, fault, "dedupe_after_restart", "dedupe identity was lost across restart"))

        except Exception as exc:
            failures.append(self._failure(episode, fault, "unhandled_exception", f"{type(exc).__name__}: {exc}"))
        return failures, operations, fault

    def run(
        self,
        episodes: int = 10_000,
        workers: int = 8,
        virtual_minutes_per_episode: float = 60.0,
        failure_sample_limit: int = 100,
    ) -> SimulationReport:
        count = max(1, int(episodes))
        worker_count = max(1, min(int(workers), 32, count))
        run_id = f"reality-{int(time.time())}-{self.seed}"
        started = time.perf_counter()
        all_failures: list[InvariantFailure] = []
        total_operations = 0
        fault_counts: Counter[str] = Counter()

        with tempfile.TemporaryDirectory(prefix="skynet-reality-") as tmp:
            base = Path(tmp)

            def run_partition(worker_id: int, episode_ids: list[int]) -> tuple[list[InvariantFailure], int, Counter[str]]:
                local_failures: list[InvariantFailure] = []
                local_operations = 0
                local_faults: Counter[str] = Counter()
                harness = _WorkerHarness(base / f"worker-{worker_id}")
                rng = random.Random(self.seed + worker_id * 1_000_003)
                try:
                    for episode_id in episode_ids:
                        failures, operations, fault = self._episode(harness, episode_id, rng)
                        local_failures.extend(failures)
                        local_operations += operations
                        local_faults[fault] += 1
                finally:
                    harness.close()
                return local_failures, local_operations, local_faults

            partitions = [list(range(i, count, worker_count)) for i in range(worker_count)]
            with ThreadPoolExecutor(max_workers=worker_count) as pool:
                results = [pool.submit(run_partition, i, ids) for i, ids in enumerate(partitions)]
                for future in results:
                    failures, operations, faults = future.result()
                    all_failures.extend(failures)
                    total_operations += operations
                    fault_counts.update(faults)

        elapsed = max(1e-9, time.perf_counter() - started)
        failed_episode_ids = {failure.episode for failure in all_failures}
        failure_counts = Counter(failure.invariant for failure in all_failures)
        report = SimulationReport(
            run_id=run_id,
            seed=self.seed,
            episodes=count,
            virtual_hours=(count * float(virtual_minutes_per_episode)) / 60.0,
            operations=total_operations,
            failed_episodes=len(failed_episode_ids),
            pass_rate=(count - len(failed_episode_ids)) / count,
            elapsed_seconds=elapsed,
            episodes_per_second=count / elapsed,
            fault_counts=dict(sorted(fault_counts.items())),
            failure_counts=dict(sorted(failure_counts.items())),
            failures=[asdict(x) for x in all_failures[:max(0, int(failure_sample_limit))]],
        )
        payload = asdict(report)
        (self.output_dir / "latest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        with (self.output_dir / "failures.jsonl").open("w", encoding="utf-8") as handle:
            for failure in all_failures:
                handle.write(json.dumps(asdict(failure), ensure_ascii=False) + "\n")
        return report

    def promote_failures(self, trajectories: TrajectoryStore, limit: int = 500) -> int:
        path = self.output_dir / "failures.jsonl"
        if not path.exists():
            return 0
        promoted = 0
        for line in path.read_text(encoding="utf-8").splitlines()[:max(0, int(limit))]:
            if not line.strip():
                continue
            item = json.loads(line)
            trajectories.record(
                session_id="reality-accelerator",
                goal=f"Synthetic invariant: {item.get('invariant', 'unknown')}",
                model="deterministic-core",
                outcome="failed",
                reward=0.0,
                evidence=f"fault={item.get('fault')} detail={item.get('detail')}",
                metadata={"source": "reality-accelerator", "episode": item.get("episode")},
            )
            promoted += 1
        return promoted


class ShadowTrajectoryAnalyzer:
    """Side-effect-free triage of historical trajectories for regression seeds."""

    FALSE_SUCCESS_TERMS = (
        "completed successfully",
        "successfully completed",
        "mission accomplished",
        "task succeeded",
        "done successfully",
    )

    def analyze(self, trajectories: TrajectoryStore, limit: int = 1000) -> dict:
        items = trajectories.recent(max(1, min(int(limit), 5000)))
        suspicious: list[dict] = []
        for item in items:
            evidence = str(item.get("evidence", ""))
            low = evidence.casefold()
            reasons: list[str] = []
            if item.get("outcome") != "success" and any(term in low for term in self.FALSE_SUCCESS_TERMS):
                reasons.append("false_success_language_on_failed_trajectory")
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            if item.get("outcome") == "success" and not evidence.strip():
                reasons.append("success_without_evidence")
            if item.get("outcome") == "success" and int(metadata.get("tool_calls", 0) or 0) > 0 and len(evidence.strip()) < 10:
                reasons.append("tool_success_with_weak_evidence")
            if reasons:
                suspicious.append({"id": item.get("id"), "session_id": item.get("session_id"), "reasons": reasons})
        return {
            "analyzed": len(items),
            "suspicious": len(suspicious),
            "suspicious_rate": (len(suspicious) / len(items)) if items else 0.0,
            "cases": suspicious[:200],
        }
