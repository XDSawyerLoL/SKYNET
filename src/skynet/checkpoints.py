from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
import threading
import time
import uuid
from typing import Any


@dataclass(slots=True)
class Checkpoint:
    id: str
    scope: str
    scope_id: str
    status: str
    state: dict[str, Any]
    created_at: float


class CheckpointStore:
    """Thread-safe durable restart-safe checkpoints for routines and long-running work."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False, timeout=10)
        with self.lock:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    scope_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_checkpoints_scope ON checkpoints(scope, scope_id, created_at DESC)"
            )
            self.conn.commit()

    def save(self, scope: str, scope_id: str, status: str, state: dict[str, Any]) -> Checkpoint:
        item = Checkpoint(uuid.uuid4().hex, scope, scope_id, status, dict(state), time.time())
        with self.lock:
            self.conn.execute(
                "INSERT INTO checkpoints(id, scope, scope_id, status, state_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (item.id, item.scope, item.scope_id, item.status, json.dumps(item.state, ensure_ascii=False), item.created_at),
            )
            self.conn.commit()
        return item

    def latest(self, scope: str, scope_id: str) -> Checkpoint | None:
        with self.lock:
            row = self.conn.execute(
                "SELECT id, scope, scope_id, status, state_json, created_at FROM checkpoints WHERE scope=? AND scope_id=? ORDER BY created_at DESC LIMIT 1",
                (scope, scope_id),
            ).fetchone()
        if not row:
            return None
        return Checkpoint(row[0], row[1], row[2], row[3], json.loads(row[4]), float(row[5]))

    def recent(self, limit: int = 50) -> list[Checkpoint]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT id, scope, scope_id, status, state_json, created_at FROM checkpoints ORDER BY created_at DESC LIMIT ?",
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [Checkpoint(r[0], r[1], r[2], r[3], json.loads(r[4]), float(r[5])) for r in rows]

    def close(self) -> None:
        with self.lock:
            self.conn.close()
