from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import hashlib
import json
import time
import uuid

from .identity import LocalIdentityStore
from .policy import canonical_json


@dataclass(slots=True)
class CapabilityLease:
    lease_id: str
    issuer_agent: str
    subject_agent: str
    capabilities: list[str]
    mandate_hash: str
    issued_at: float
    valid_until: float
    max_calls: int = 1
    metadata: dict = field(default_factory=dict)
    signature: str = ""

    @property
    def digest(self) -> str:
        data = asdict(self)
        data["signature"] = ""
        return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


class CapabilityLeaseStore:
    """Local signed, time-bounded delegation primitive.

    Designed to map later to A2A credentials, OAuth delegation or wallet policy
    systems while preserving SKYNET's canonical local authorization boundary.
    """

    def __init__(self, path: Path, identity: LocalIdentityStore) -> None:
        self.path = path
        self.identity = identity
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

    def issue(
        self,
        subject_agent: str,
        capabilities: list[str],
        mandate_hash: str,
        ttl_seconds: int = 900,
        max_calls: int = 1,
        metadata: dict | None = None,
    ) -> CapabilityLease:
        now = time.time()
        clean_caps = sorted({c.strip() for c in capabilities if c.strip()})
        if not clean_caps:
            raise ValueError("at least one capability is required")
        lease = CapabilityLease(
            lease_id=uuid.uuid4().hex,
            issuer_agent=self.identity.identity.agent_id,
            subject_agent=subject_agent,
            capabilities=clean_caps,
            mandate_hash=mandate_hash,
            issued_at=now,
            valid_until=now + max(1, min(int(ttl_seconds), 86400)),
            max_calls=max(1, min(int(max_calls), 1000)),
            metadata=metadata or {},
        )
        lease.signature = self.identity.sign(lease.digest.encode("ascii"))
        data = self._load()
        data[lease.lease_id] = {**asdict(lease), "used_calls": 0, "revoked": False}
        self._save(data)
        return lease

    def verify(self, lease_id: str, capability: str, subject_agent: str, mandate_hash: str) -> tuple[bool, str]:
        raw = self._load().get(lease_id)
        if raw is None:
            return False, "unknown lease"
        if raw.get("revoked"):
            return False, "lease revoked"
        used = int(raw.get("used_calls", 0))
        lease_data = {k: v for k, v in raw.items() if k not in {"used_calls", "revoked"}}
        lease = CapabilityLease(**lease_data)
        if not self.identity.verify(lease.digest.encode("ascii"), lease.signature):
            return False, "invalid signature"
        if time.time() > lease.valid_until:
            return False, "lease expired"
        if lease.subject_agent != subject_agent:
            return False, "subject mismatch"
        if lease.mandate_hash != mandate_hash:
            return False, "mandate mismatch"
        if capability not in lease.capabilities and "*" not in lease.capabilities:
            return False, "capability not delegated"
        if used >= lease.max_calls:
            return False, "lease call budget exhausted"
        return True, "valid"

    def consume(self, lease_id: str, capability: str, subject_agent: str, mandate_hash: str) -> tuple[bool, str]:
        ok, reason = self.verify(lease_id, capability, subject_agent, mandate_hash)
        if not ok:
            return ok, reason
        data = self._load()
        data[lease_id]["used_calls"] = int(data[lease_id].get("used_calls", 0)) + 1
        self._save(data)
        return True, "consumed"

    def revoke(self, lease_id: str) -> bool:
        data = self._load()
        if lease_id not in data:
            return False
        data[lease_id]["revoked"] = True
        self._save(data)
        return True

    def list(self) -> list[dict]:
        return list(self._load().values())
