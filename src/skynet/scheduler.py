from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
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


class RoutineStore:
    """Local interval scheduler persisted in SQLite."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
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
                last_run REAL
            )
            """
        )
        self.conn.commit()

    @staticmethod
    def _row(row: tuple) -> Routine:
        return Routine(
            id=str(row[0]), name=str(row[1]), prompt=str(row[2]), interval_seconds=int(row[3]),
            next_run=float(row[4]), enabled=bool(row[5]), last_status=str(row[6]),
            last_run=None if row[7] is None else float(row[7]),
        )

    def create(self, name: str, prompt: str, interval_seconds: int, start_in_seconds: int = 0) -> Routine:
        clean_name = name.strip()
        clean_prompt = prompt.strip()
        if not clean_name or not clean_prompt:
            raise ValueError("Routine name and prompt are required")
        interval = int(interval_seconds)
        if interval < 60:
            raise ValueError("Minimum routine interval is 60 seconds")
        start = max(0, int(start_in_seconds))
        item = Routine(uuid.uuid4().hex[:12], clean_name, clean_prompt, interval, time.time() + start, True, "never", None)
        self.conn.execute(
            "INSERT INTO routines(id,name,prompt,interval_seconds,next_run,enabled,last_status,last_run) VALUES(?,?,?,?,?,?,?,?)",
            (item.id, item.name, item.prompt, item.interval_seconds, item.next_run, 1, item.last_status, item.last_run),
        )
        self.conn.commit()
        return item

    def list(self) -> list[Routine]:
        rows = self.conn.execute(
            "SELECT id,name,prompt,interval_seconds,next_run,enabled,last_status,last_run FROM routines ORDER BY name"
        ).fetchall()
        return [self._row(r) for r in rows]

    def get(self, routine_id: str) -> Routine | None:
        row = self.conn.execute(
            "SELECT id,name,prompt,interval_seconds,next_run,enabled,last_status,last_run FROM routines WHERE id=?",
            (routine_id,),
        ).fetchone()
        return None if row is None else self._row(row)

    def due(self, now: float | None = None, limit: int = 20) -> list[Routine]:
        moment = time.time() if now is None else float(now)
        rows = self.conn.execute(
            "SELECT id,name,prompt,interval_seconds,next_run,enabled,last_status,last_run FROM routines WHERE enabled=1 AND next_run<=? ORDER BY next_run LIMIT ?",
            (moment, max(1, min(limit, 100))),
        ).fetchall()
        return [self._row(r) for r in rows]

    def mark_result(self, routine_id: str, status: str, now: float | None = None) -> None:
        moment = time.time() if now is None else float(now)
        current = self.get(routine_id)
        if current is None:
            raise KeyError(routine_id)
        self.conn.execute(
            "UPDATE routines SET last_status=?, last_run=?, next_run=? WHERE id=?",
            (status, moment, moment + current.interval_seconds, routine_id),
        )
        self.conn.commit()

    def set_enabled(self, routine_id: str, enabled: bool) -> None:
        self.conn.execute("UPDATE routines SET enabled=? WHERE id=?", (1 if enabled else 0, routine_id))
        self.conn.commit()

    def delete(self, routine_id: str) -> None:
        self.conn.execute("DELETE FROM routines WHERE id=?", (routine_id,))
        self.conn.commit()

    def render(self, item: Routine) -> str:
        state = "enabled" if item.enabled else "disabled"
        return f"{item.id} | {item.name} | every {item.interval_seconds}s | {state} | last={item.last_status}"

    def close(self) -> None:
        self.conn.close()
