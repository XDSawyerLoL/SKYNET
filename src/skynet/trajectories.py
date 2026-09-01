from __future__ import annotations

from pathlib import Path
import json
import sqlite3
import threading
import time


class TrajectoryStore:
    """Thread-safe evidence store for successful and failed agent trajectories."""

    def __init__(self, path: Path) -> None:
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=10)
        with self.lock:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS trajectories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    session_id TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    model TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    reward REAL NOT NULL,
                    evidence TEXT NOT NULL,
                    metadata TEXT NOT NULL
                )
            """)
            self.db.commit()

    def record(
        self,
        session_id: str,
        goal: str,
        model: str,
        outcome: str,
        reward: float,
        evidence: str,
        metadata: dict | None = None,
    ) -> int:
        with self.lock:
            cur = self.db.execute(
                "INSERT INTO trajectories(ts,session_id,goal,model,outcome,reward,evidence,metadata) VALUES(?,?,?,?,?,?,?,?)",
                (time.time(), session_id, goal, model, outcome, float(reward), evidence[:100_000], json.dumps(metadata or {}, ensure_ascii=False)),
            )
            self.db.commit()
            return int(cur.lastrowid)

    def recent(self, limit: int = 20) -> list[dict]:
        with self.lock:
            rows = self.db.execute(
                "SELECT id,ts,session_id,goal,model,outcome,reward,evidence,metadata FROM trajectories ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 100)),),
            ).fetchall()
        keys = ("id", "ts", "session_id", "goal", "model", "outcome", "reward", "evidence", "metadata")
        output = []
        for row in rows:
            item = dict(zip(keys, row))
            item["metadata"] = json.loads(item["metadata"])
            output.append(item)
        return output

    def best(self, limit: int = 20) -> list[dict]:
        with self.lock:
            rows = self.db.execute(
                "SELECT id,ts,session_id,goal,model,outcome,reward,evidence,metadata FROM trajectories WHERE outcome='success' ORDER BY reward DESC, id DESC LIMIT ?",
                (max(1, min(limit, 100)),),
            ).fetchall()
        keys = ("id", "ts", "session_id", "goal", "model", "outcome", "reward", "evidence", "metadata")
        return [{**dict(zip(keys, row)), "metadata": json.loads(row[-1])} for row in rows]

    def close(self) -> None:
        with self.lock:
            self.db.close()
