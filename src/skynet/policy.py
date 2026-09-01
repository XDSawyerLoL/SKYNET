from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import hashlib
import json
import sqlite3
import threading
import time
import uuid

from .identity import LocalIdentityStore


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(slots=True)
class Mandate:
    mandate_id: str
    principal: str
    agent_id: str
    allowed_actions: list[str] = field(default_factory=lambda: ["*"])
    blocked_actions: list[str] = field(default_factory=list)
    allowed_targets: list[str] = field(default_factory=lambda: ["*"])
    blocked_targets: list[str] = field(default_factory=list)
    max_value_per_action: int | None = None
    max_value_per_day: int | None = None
    valid_after: float = 0.0
    valid_until: float = 4102444800.0
    max_risk_score: int = 100
    reversible_only: bool = False
    require_human: bool = False
    metadata: dict = field(default_factory=dict)

    @property
    def policy_hash(self) -> str:
        return hashlib.sha256(canonical_json(asdict(self)).encode("utf-8")).hexdigest()


@dataclass(slots=True)
class ActionRequest:
    action: str
    agent_id: str
    target: str = "local"
    value: int = 0
    risk_score: int = 0
    reversible: bool = True
    nonce: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: float = field(default_factory=time.time)
    parameters: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ActionDecision:
    allowed: bool
    code: str
    reason: str
    policy_hash: str


class MandateStore:
    def __init__(self, path: Path, agent_id: str) -> None:
        self.path = path
        self.agent_id = agent_id
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.save(Mandate(
                mandate_id="local-owner-default",
                principal="local-owner",
                agent_id=agent_id,
                metadata={"source": "SKYNET default local mandate", "version": 1},
            ))

    def load(self) -> Mandate:
        return Mandate(**json.loads(self.path.read_text(encoding="utf-8")))

    def save(self, mandate: Mandate) -> None:
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(asdict(mandate), ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)


class ReceiptStore:
    def __init__(self, path: Path, identity: LocalIdentityStore) -> None:
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=10)
        self.identity = identity
        with self.lock:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS receipts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    nonce TEXT NOT NULL UNIQUE,
                    policy_hash TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target TEXT NOT NULL,
                    value INTEGER NOT NULL,
                    decision TEXT NOT NULL,
                    result TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    entry_hash TEXT NOT NULL,
                    signature TEXT NOT NULL
                )
            """)
            self.db.commit()

    def nonce_seen(self, nonce: str) -> bool:
        with self.lock:
            return self.db.execute("SELECT 1 FROM receipts WHERE nonce=?", (nonce,)).fetchone() is not None

    def spent_since(self, policy_hash: str, since: float) -> int:
        with self.lock:
            row = self.db.execute(
                "SELECT COALESCE(SUM(value),0) FROM receipts WHERE policy_hash=? AND ts>=? AND decision='allowed' AND result='ok'",
                (policy_hash, since),
            ).fetchone()
        return int(row[0] or 0)

    def append(self, request: ActionRequest, decision: ActionDecision, result: str) -> str:
        with self.lock:
            row = self.db.execute("SELECT entry_hash FROM receipts ORDER BY id DESC LIMIT 1").fetchone()
            previous = row[0] if row else "0" * 64
            payload = {
                "ts": request.timestamp,
                "nonce": request.nonce,
                "policy_hash": decision.policy_hash,
                "action": request.action,
                "target": request.target,
                "value": request.value,
                "decision": "allowed" if decision.allowed else "denied",
                "result": result,
                "previous_hash": previous,
            }
            entry_hash = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
            signature = self.identity.sign(entry_hash.encode("ascii"))
            self.db.execute(
                "INSERT INTO receipts(ts,nonce,policy_hash,action,target,value,decision,result,previous_hash,entry_hash,signature) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (request.timestamp, request.nonce, decision.policy_hash, request.action, request.target, request.value,
                 payload["decision"], result, previous, entry_hash, signature),
            )
            self.db.commit()
            return entry_hash

    def recent(self, limit: int = 20) -> list[dict]:
        with self.lock:
            rows = self.db.execute(
                "SELECT ts,action,target,value,decision,result,entry_hash FROM receipts ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(zip(("ts", "action", "target", "value", "decision", "result", "hash"), row)) for row in rows]

    def verify_chain(self) -> bool:
        previous = "0" * 64
        with self.lock:
            rows = self.db.execute(
                "SELECT ts,nonce,policy_hash,action,target,value,decision,result,previous_hash,entry_hash,signature FROM receipts ORDER BY id"
            ).fetchall()
        for row in rows:
            ts, nonce, policy_hash, action, target, value, decision, result, prev, entry_hash, signature = row
            if prev != previous:
                return False
            payload = {
                "ts": ts, "nonce": nonce, "policy_hash": policy_hash, "action": action, "target": target,
                "value": value, "decision": decision, "result": result, "previous_hash": prev,
            }
            expected = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
            if expected != entry_hash or not self.identity.verify(entry_hash.encode("ascii"), signature):
                return False
            previous = entry_hash
        return True

    def close(self) -> None:
        with self.lock:
            self.db.close()


class PolicyEngine:
    """Deterministic policy enforcement. The LLM never decides whether a policy passes."""

    def __init__(self, receipts: ReceiptStore) -> None:
        self.receipts = receipts

    @staticmethod
    def _matches(value: str, patterns: list[str]) -> bool:
        return "*" in patterns or value in patterns

    def evaluate(self, mandate: Mandate, request: ActionRequest) -> ActionDecision:
        ph = mandate.policy_hash
        deny = lambda code, reason: ActionDecision(False, code, reason, ph)
        allow = lambda: ActionDecision(True, "allowed", "action satisfies mandate", ph)
        if request.agent_id != mandate.agent_id:
            return deny("agent_mismatch", "agent identity is not authorized by mandate")
        if request.timestamp < mandate.valid_after or request.timestamp > mandate.valid_until:
            return deny("expired", "mandate is not active at this time")
        if self.receipts.nonce_seen(request.nonce):
            return deny("replay", "action nonce was already used")
        if request.action in mandate.blocked_actions or not self._matches(request.action, mandate.allowed_actions):
            return deny("action_blocked", "action is outside allowed mandate actions")
        if request.target in mandate.blocked_targets or not self._matches(request.target, mandate.allowed_targets):
            return deny("target_blocked", "target is outside allowed mandate targets")
        if mandate.max_value_per_action is not None and request.value > mandate.max_value_per_action:
            return deny("value_limit", "action exceeds per-action value limit")
        if mandate.max_value_per_day is not None:
            day_start = request.timestamp - (request.timestamp % 86400)
            if self.receipts.spent_since(ph, day_start) + request.value > mandate.max_value_per_day:
                return deny("daily_limit", "action exceeds daily value limit")
        if request.risk_score > mandate.max_risk_score:
            return deny("risk_limit", "action risk score exceeds mandate threshold")
        if mandate.reversible_only and not request.reversible:
            return deny("irreversible", "mandate allows only reversible actions")
        if mandate.require_human:
            return deny("human_required", "mandate requires explicit human authorization")
        return allow()
