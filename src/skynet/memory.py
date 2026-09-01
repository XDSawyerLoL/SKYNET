from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime, timezone


class MemoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        self.db.commit()

    def add_message(self, session_id: str, role: str, content: str) -> None:
        self.db.execute(
            "INSERT INTO messages(session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, datetime.now(timezone.utc).isoformat()),
        )
        self.db.commit()

    def recent_messages(self, session_id: str, limit: int = 30) -> list[dict]:
        rows = self.db.execute(
            "SELECT role, content FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

    def remember(self, content: str) -> str:
        clean = content.strip()
        if not clean:
            raise ValueError("Memory cannot be empty")
        self.db.execute(
            "INSERT INTO memories(content, created_at) VALUES (?, ?)",
            (clean, datetime.now(timezone.utc).isoformat()),
        )
        self.db.commit()
        return "Memory stored."

    def list_memories(self, limit: int = 20) -> list[str]:
        rows = self.db.execute(
            "SELECT content FROM memories ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [row["content"] for row in reversed(rows)]

    def close(self) -> None:
        self.db.close()
