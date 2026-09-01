from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
import threading
import time
import uuid


@dataclass(slots=True)
class Routine:
    id: str
    name: str
    prompt: str
    interval_seconds: int
    next_run: float
    enabled: bool
    last_status: str
    last_run: float | None
    session_id: str = "autonomy"
    trigger: str = "interval"
    max_runs: int | None = None
    run_count: int = 0


class RoutineStore:
    """Thread-safe persistent conversation-bound local automation scheduler."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False, timeout=10)
        with self.lock:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS routines (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    interval_seconds INTEGER NOT NULL,
                    next_run REAL NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_status TEXT NOT NULL DEFAULT 'never',
                    last_run REAL,
                    session_id TEXT NOT NULL DEFAULT 'autonomy',
                    trigger TEXT NOT NULL DEFAULT 'interval',
                    max_runs INTEGER,
                    run_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            columns = {str(row[1]) for row in self.conn.execute("PRAGMA table_info(routines)").fetchall()}
            migrations = {
                "session_id": "ALTER TABLE routines ADD COLUMN session_id TEXT NOT NULL DEFAULT 'autonomy'",
                "trigger": "ALTER TABLE routines ADD COLUMN trigger TEXT NOT NULL DEFAULT 'interval'",
                "max_runs": "ALTER TABLE routines ADD COLUMN max_runs INTEGER",
                "run_count": "ALTER TABLE routines ADD COLUMN run_count INTEGER NOT NULL DEFAULT 0",
            }
            for column, sql in migrations.items():
                if column not in columns:
                    self.conn.execute(sql)
            self.conn.commit()

    @staticmethod
    def _row(row: tuple) -> Routine:
        return Routine(
            id=str(row[0]), name=str(row[1]), prompt=str(row[2]), interval_seconds=int(row[3]),
            next_run=float(row[4]), enabled=bool(row[5]), last_status=str(row[6]),
            last_run=None if row[7] is None else float(row[7]), session_id=str(row[8] or "autonomy"),
            trigger=str(row[9] or "interval"), max_runs=None if row[10] is None else int(row[10]), run_count=int(row[11] or 0),
        )

    @staticmethod
    def _select() -> str:
        return "id,name,prompt,interval_seconds,next_run,enabled,last_status,last_run,session_id,trigger,max_runs,run_count"

    def create(self, name: str, prompt: str, interval_seconds: int, start_in_seconds: int = 0,
               session_id: str = "autonomy", max_runs: int | None = None) -> Routine:
        clean_name = name.strip(); clean_prompt = prompt.strip()
        if not clean_name or not clean_prompt:
            raise ValueError("Routine name and prompt are required")
        interval = int(interval_seconds)
        if interval < 60:
            raise ValueError("Minimum routine interval is 60 seconds")
        if max_runs is not None and int(max_runs) < 1:
            raise ValueError("max_runs must be >= 1")
        item = Routine(uuid.uuid4().hex[:12], clean_name, clean_prompt, interval, time.time() + max(0, int(start_in_seconds)),
                       True, "never", None, session_id.strip()[:128] or "autonomy", "interval", max_runs, 0)
        self._insert(item); return item

    def create_once(self, name: str, prompt: str, run_at: float, session_id: str = "autonomy") -> Routine:
        moment = float(run_at)
        if moment < time.time() - 5:
            raise ValueError("one-shot run time is in the past")
        item = Routine(uuid.uuid4().hex[:12], name.strip(), prompt.strip(), 60, moment, True, "never", None,
                       session_id.strip()[:128] or "autonomy", "once", 1, 0)
        if not item.name or not item.prompt:
            raise ValueError("Routine name and prompt are required")
        self._insert(item); return item

    def _insert(self, item: Routine) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT INTO routines(id,name,prompt,interval_seconds,next_run,enabled,last_status,last_run,session_id,trigger,max_runs,run_count) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (item.id, item.name, item.prompt, item.interval_seconds, item.next_run, 1, item.last_status, item.last_run,
                 item.session_id, item.trigger, item.max_runs, item.run_count),
            )
            self.conn.commit()

    def list(self) -> list[Routine]:
        with self.lock:
            rows = self.conn.execute(f"SELECT {self._select()} FROM routines ORDER BY name").fetchall()
        return [self._row(r) for r in rows]

    def get(self, routine_id: str) -> Routine | None:
        with self.lock:
            row = self.conn.execute(f"SELECT {self._select()} FROM routines WHERE id=?", (routine_id,)).fetchone()
        return None if row is None else self._row(row)

    def due(self, now: float | None = None, limit: int = 20) -> list[Routine]:
        moment = time.time() if now is None else float(now)
        with self.lock:
            rows = self.conn.execute(
                f"SELECT {self._select()} FROM routines WHERE enabled=1 AND next_run<=? ORDER BY next_run LIMIT ?",
                (moment, max(1, min(limit, 100))),
            ).fetchall()
        return [self._row(r) for r in rows]

    def mark_result(self, routine_id: str, status: str, now: float | None = None) -> None:
        moment = time.time() if now is None else float(now)
        with self.lock:
            row = self.conn.execute(f"SELECT {self._select()} FROM routines WHERE id=?", (routine_id,)).fetchone()
            if row is None:
                raise KeyError(routine_id)
            current = self._row(row)
            new_count = current.run_count + 1
            disable = current.trigger == "once" or (current.max_runs is not None and new_count >= current.max_runs)
            self.conn.execute(
                "UPDATE routines SET last_status=?, last_run=?, next_run=?, run_count=?, enabled=? WHERE id=?",
                (status, moment, moment + current.interval_seconds, new_count, 0 if disable else 1, routine_id),
            )
            self.conn.commit()

    def set_enabled(self, routine_id: str, enabled: bool) -> None:
        with self.lock:
            self.conn.execute("UPDATE routines SET enabled=? WHERE id=?", (1 if enabled else 0, routine_id)); self.conn.commit()

    def delete(self, routine_id: str) -> None:
        with self.lock:
            self.conn.execute("DELETE FROM routines WHERE id=?", (routine_id,)); self.conn.commit()

    def render(self, item: Routine) -> str:
        state = "enabled" if item.enabled else "disabled"
        runs = f"{item.run_count}/{item.max_runs}" if item.max_runs is not None else str(item.run_count)
        return f"{item.id} | {item.name} | {item.trigger} every {item.interval_seconds}s | session={item.session_id} | {state} | runs={runs} | last={item.last_status}"

    def close(self) -> None:
        with self.lock:
            self.conn.close()
