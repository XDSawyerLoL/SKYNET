from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
import json
import random
import time

from .permissions import PermissionGate
from .policy import ActionRequest, Mandate, PolicyEngine


POLICY_CASES = (
    "valid",
    "agent_mismatch",
    "expired",
    "replay",
    "action_blocked",
    "target_blocked",
    "value_limit",
    "daily_limit",
    "risk_limit",
    "irreversible",
    "human_required",
)

EXPECTED_CODES = {
    "valid": "allowed",
    "agent_mismatch": "agent_mismatch",
    "expired": "expired",
    "replay": "replay",
    "action_blocked": "action_blocked",
    "target_blocked": "target_blocked",
    "value_limit": "value_limit",
    "daily_limit": "daily_limit",
    "risk_limit": "risk_limit",
    "irreversible": "irreversible",
    "human_required": "human_required",
}


class _MemoryReceiptOracle:
    def __init__(self) -> None:
        self.seen: set[str] = set()
        self.spent = 0

    def nonce_seen(self, nonce: str) -> bool:
        return nonce in self.seen

    def spent_since(self, policy_hash: str, since: float) -> int:
        return self.spent


@dataclass(frozen=True, slots=True)
class FuzzFailure:
    case: int
    scenario: str
    expected: str
    actual: str
    detail: str


@dataclass(frozen=True, slots=True)
class FuzzReport:
    seed: int
    cases: int
    passed: int
    pass_rate: float
    elapsed_seconds: float
    cases_per_second: float
    scenario_counts: dict[str, int]
    permission_checks: int
    failures: list[dict]


class FastPolicyFuzzer:
    """High-throughput deterministic mutation/fuzz lane for governance logic.

    This lane deliberately avoids filesystem/database I/O. The deeper Reality
    Accelerator separately tests persistence/restart behavior. Together they
    provide breadth + depth without pretending synthetic tests equal field use.
    """

    def __init__(self, output_dir: Path, seed: int = 8196) -> None:
        self.output_dir = output_dir.resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.seed = int(seed)

    @staticmethod
    def _base(now: float, nonce: str) -> tuple[Mandate, ActionRequest]:
        agent = "agent-local"
        mandate = Mandate(
            mandate_id="fuzz",
            principal="owner",
            agent_id=agent,
            allowed_actions=["read_file", "write_file"],
            blocked_actions=[],
            allowed_targets=["workspace"],
            blocked_targets=[],
            max_value_per_action=100,
            max_value_per_day=500,
            valid_after=now - 60,
            valid_until=now + 60,
            max_risk_score=50,
            reversible_only=False,
            require_human=False,
        )
        request = ActionRequest(
            action="read_file",
            agent_id=agent,
            target="workspace",
            value=0,
            risk_score=5,
            reversible=True,
            nonce=nonce,
            timestamp=now,
        )
        return mandate, request

    def _mutate(self, scenario: str, now: float, nonce: str, receipts: _MemoryReceiptOracle) -> tuple[Mandate, ActionRequest]:
        mandate, request = self._base(now, nonce)
        if scenario == "agent_mismatch":
            request.agent_id = "other-agent"
        elif scenario == "expired":
            mandate.valid_until = now - 1
        elif scenario == "replay":
            receipts.seen.add(nonce)
        elif scenario == "action_blocked":
            mandate.blocked_actions = ["read_file"]
        elif scenario == "target_blocked":
            mandate.blocked_targets = ["workspace"]
        elif scenario == "value_limit":
            request.value = 101
        elif scenario == "daily_limit":
            request.value = 10
            receipts.spent = 495
        elif scenario == "risk_limit":
            request.risk_score = 51
        elif scenario == "irreversible":
            mandate.reversible_only = True
            request.reversible = False
        elif scenario == "human_required":
            mandate.require_human = True
        return mandate, request

    @staticmethod
    def _permission_oracle(gate: PermissionGate, rng: random.Random) -> tuple[int, list[str]]:
        failures: list[str] = []
        checks = 0
        # Observe must not need approval.
        checks += 1
        if not gate.authorize("read_file", "read", lambda _m: False):
            failures.append("observe_denied")
        # Confirmation must respect both denial and approval.
        checks += 1
        if gate.authorize("write_file", "write", lambda _m: False):
            failures.append("confirmation_bypass")
        checks += 1
        if not gate.authorize("write_file", "write", lambda _m: True):
            failures.append("confirmation_not_honored")
        # Unknown tools default deny regardless of confirmer.
        checks += 1
        unknown = f"unknown_{rng.randrange(1_000_000_000)}"
        if gate.authorize(unknown, "unknown", lambda _m: True):
            failures.append("unknown_tool_allowed")
        return checks, failures

    def run(self, cases: int = 100_000, failure_sample_limit: int = 100) -> FuzzReport:
        count = max(1, int(cases))
        rng = random.Random(self.seed)
        gate = PermissionGate()
        failures: list[FuzzFailure] = []
        scenarios: Counter[str] = Counter()
        permission_checks = 0
        started = time.perf_counter()

        for index in range(count):
            scenario = POLICY_CASES[index % len(POLICY_CASES)]
            scenarios[scenario] += 1
            now = 1_800_000_000.0 + (index % 1000)
            nonce = f"fuzz-{self.seed}-{index}-{rng.randrange(1_000_000_000)}"
            receipts = _MemoryReceiptOracle()
            engine = PolicyEngine(receipts)  # type: ignore[arg-type]
            mandate, request = self._mutate(scenario, now, nonce, receipts)
            decision = engine.evaluate(mandate, request)
            expected = EXPECTED_CODES[scenario]
            if decision.code != expected or decision.allowed != (scenario == "valid"):
                failures.append(FuzzFailure(index, scenario, expected, decision.code, decision.reason))

            checks, permission_failures = self._permission_oracle(gate, rng)
            permission_checks += checks
            for detail in permission_failures:
                failures.append(FuzzFailure(index, "permission_gate", "invariant", detail, detail))

        elapsed = max(1e-9, time.perf_counter() - started)
        report = FuzzReport(
            seed=self.seed,
            cases=count,
            passed=count - len({failure.case for failure in failures}),
            pass_rate=(count - len({failure.case for failure in failures})) / count,
            elapsed_seconds=elapsed,
            cases_per_second=count / elapsed,
            scenario_counts=dict(sorted(scenarios.items())),
            permission_checks=permission_checks,
            failures=[asdict(x) for x in failures[:max(0, int(failure_sample_limit))]],
        )
        (self.output_dir / "fuzz-latest.json").write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8")
        return report
