from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
import threading
import time


@dataclass(frozen=True, slots=True)
class ModelStats:
    model: str
    samples: int
    avg_latency_s: float
    avg_tokens_per_s: float | None
    avg_energy_wh: float | None
    avg_gpu_memory_mb: float | None
    avg_ram_delta_mb: float | None


class ModelTelemetryStore:
    """Local performance evidence for adaptive routing."""

    def __init__(self, path: Path) -> None:
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.RLock()
        with self.lock:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS model_telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    model TEXT NOT NULL,
                    task_class TEXT NOT NULL,
                    latency_s REAL NOT NULL,
                    tokens_per_s REAL,
                    energy_wh REAL,
                    gpu_memory_mb REAL,
                    ram_delta_mb REAL,
                    success INTEGER NOT NULL
                )
            """)
            columns = {row[1] for row in self.db.execute("PRAGMA table_info(model_telemetry)").fetchall()}
            if "ram_delta_mb" not in columns:
                self.db.execute("ALTER TABLE model_telemetry ADD COLUMN ram_delta_mb REAL")
            self.db.commit()

    def record(
        self,
        model: str,
        task_class: str,
        latency_s: float,
        tokens_per_s: float | None = None,
        energy_wh: float | None = None,
        gpu_memory_mb: float | None = None,
        ram_delta_mb: float | None = None,
        success: bool = True,
    ) -> None:
        with self.lock:
            self.db.execute(
                "INSERT INTO model_telemetry(ts,model,task_class,latency_s,tokens_per_s,energy_wh,gpu_memory_mb,ram_delta_mb,success) VALUES(?,?,?,?,?,?,?,?,?)",
                (time.time(), model, task_class, float(latency_s), tokens_per_s, energy_wh, gpu_memory_mb, ram_delta_mb, 1 if success else 0),
            )
            self.db.commit()

    def stats(self, model: str, task_class: str | None = None, limit: int = 50) -> ModelStats | None:
        params: list[object] = [model]
        where = "model=? AND success=1"
        if task_class:
            where += " AND task_class=?"
            params.append(task_class)
        params.append(max(1, min(limit, 500)))
        with self.lock:
            rows = self.db.execute(
                f"SELECT latency_s,tokens_per_s,energy_wh,gpu_memory_mb,ram_delta_mb FROM model_telemetry WHERE {where} ORDER BY id DESC LIMIT ?",
                tuple(params),
            ).fetchall()
        if not rows:
            return None

        def avg(index: int) -> float | None:
            values = [float(row[index]) for row in rows if row[index] is not None]
            return sum(values) / len(values) if values else None

        return ModelStats(
            model=model,
            samples=len(rows),
            avg_latency_s=sum(float(row[0]) for row in rows) / len(rows),
            avg_tokens_per_s=avg(1),
            avg_energy_wh=avg(2),
            avg_gpu_memory_mb=avg(3),
            avg_ram_delta_mb=avg(4),
        )

    def recent(self, limit: int = 30) -> list[dict]:
        with self.lock:
            rows = self.db.execute(
                "SELECT ts,model,task_class,latency_s,tokens_per_s,energy_wh,gpu_memory_mb,ram_delta_mb,success FROM model_telemetry ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 200)),),
            ).fetchall()
        keys = ("ts", "model", "task_class", "latency_s", "tokens_per_s", "energy_wh", "gpu_memory_mb", "ram_delta_mb", "success")
        return [dict(zip(keys, row)) for row in rows]

    def close(self) -> None:
        with self.lock:
            self.db.close()
