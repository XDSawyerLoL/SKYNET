from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLog:
    """Append-only JSONL audit log with a simple hash chain."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._last_hash = self._load_last_hash()

    def _load_last_hash(self) -> str:
        if not self.path.exists():
            return "GENESIS"
        last = ""
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last = line
        if not last:
            return "GENESIS"
        try:
            return json.loads(last).get("hash", "GENESIS")
        except json.JSONDecodeError:
            return "BROKEN_CHAIN"

    def record(self, action: str, details: dict[str, Any], outcome: str) -> None:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "details": details,
            "outcome": outcome,
            "previous_hash": self._last_hash,
        }
        canonical = json.dumps(event, ensure_ascii=False, sort_keys=True).encode("utf-8")
        event_hash = hashlib.sha256(canonical).hexdigest()
        event["hash"] = event_hash
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        self._last_hash = event_hash
