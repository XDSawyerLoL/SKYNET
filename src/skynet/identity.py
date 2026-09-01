from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import hmac
import os
import secrets


@dataclass(frozen=True, slots=True)
class AgentIdentity:
    agent_id: str
    fingerprint: str


class LocalIdentityStore:
    """Local signing identity.

    V0.4 deliberately uses an HMAC key for local tamper evidence without adding a
    crypto dependency. External/public-key identities are adapters, not a core
    requirement. The key never leaves the local data directory.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._key = self._load_or_create()
        digest = hashlib.sha256(self._key).hexdigest()
        self.identity = AgentIdentity(agent_id=f"skynet:{digest[:24]}", fingerprint=digest)

    def _load_or_create(self) -> bytes:
        if self.path.exists():
            raw = self.path.read_text(encoding="ascii").strip()
            return bytes.fromhex(raw)
        key = secrets.token_bytes(32)
        self.path.write_text(key.hex(), encoding="ascii")
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass
        return key

    def sign(self, payload: bytes) -> str:
        return hmac.new(self._key, payload, hashlib.sha256).hexdigest()

    def verify(self, payload: bytes, signature: str) -> bool:
        return hmac.compare_digest(self.sign(payload), signature)
