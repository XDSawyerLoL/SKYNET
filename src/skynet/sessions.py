from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
import time
import uuid


@dataclass(frozen=True, slots=True)
class SessionInfo:
    session_id: str
    title: str
    project: str
    channel: str
    created_at: float
    updated_at: float
    archived: bool


class SessionStore:
    """Durable session metadata and conversation search over SKYNET memory.db.

    The existing messages table remains the source of conversation text. This
    store adds product-level organization without duplicating message history.
    """

    def __init__(self, memory_db: Path) -> None:
        self.path = memory_db
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                project TEXT NOT NULL DEFAULT '',
                channel TEXT NOT NULL DEFAULT 'local',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                archived INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self.db.commit()

    def ensure(self, session_id: str, title: str | None = None, project: str = "", channel: str = "local") -> SessionInfo:
        clean_id = session_id.strip()
        if not clean_id or len(clean_id) > 128:
            raise ValueError("invalid session id")
        row = self.db.execute("SELECT * FROM sessions WHERE session_id=?", (clean_id,)).fetchone()
        now = time.time()
        if row is None:
            clean_title = (title or clean_id).strip()[:160] or clean_id
            self.db.execute(
                "INSERT INTO sessions(session_id,title,project,channel,created_at,updated_at,archived) VALUES(?,?,?,?,?,?,0)",
                (clean_id, clean_title, project.strip()[:160], channel.strip()[:64] or "local", now, now),
            )
            self.db.commit()
        else:
            self.db.execute("UPDATE sessions SET updated_at=? WHERE session_id=?", (now, clean_id))
            self.db.commit()
        return self.get(clean_id)

    def create(self, title: str, project: str = "", channel: str = "local") -> SessionInfo:
        session_id = uuid.uuid4().hex[:16]
        return self.ensure(session_id, title=title, project=project, channel=channel)

    def get(self, session_id: str) -> SessionInfo:
        row = self.db.execute("SELECT * FROM sessions WHERE session_id=?", (session_id,)).fetchone()
        if row is None:
            raise KeyError(session_id)
        return SessionInfo(
            str(row["session_id"]), str(row["title"]), str(row["project"]), str(row["channel"]),
            float(row["created_at"]), float(row["updated_at"]), bool(row["archived"]),
        )

    def rename(self, session_id: str, title: str) -> SessionInfo:
        clean = title.strip()[:160]
        if not clean:
            raise ValueError("session title cannot be empty")
        self.db.execute("UPDATE sessions SET title=?, updated_at=? WHERE session_id=?", (clean, time.time(), session_id))
        self.db.commit()
        return self.get(session_id)

    def set_project(self, session_id: str, project: str) -> SessionInfo:
        self.db.execute("UPDATE sessions SET project=?, updated_at=? WHERE session_id=?", (project.strip()[:160], time.time(), session_id))
        self.db.commit()
        return self.get(session_id)

    def archive(self, session_id: str, archived: bool = True) -> SessionInfo:
        self.db.execute("UPDATE sessions SET archived=?, updated_at=? WHERE session_id=?", (1 if archived else 0, time.time(), session_id))
        self.db.commit()
        return self.get(session_id)

    def list(self, include_archived: bool = False, limit: int = 100) -> list[SessionInfo]:
        where = "" if include_archived else "WHERE archived=0"
        rows = self.db.execute(
            f"SELECT * FROM sessions {where} ORDER BY updated_at DESC LIMIT ?", (max(1, min(limit, 500)),)
        ).fetchall()
        return [SessionInfo(str(r["session_id"]), str(r["title"]), str(r["project"]), str(r["channel"]),
                            float(r["created_at"]), float(r["updated_at"]), bool(r["archived"])) for r in rows]

    def search(self, query: str, limit: int = 50) -> list[dict]:
        clean = query.strip()
        if not clean:
            return []
        needle = f"%{clean.replace('%', '').replace('_', '')}%"
        rows = self.db.execute(
            """
            SELECT m.session_id, m.role, m.content, m.created_at,
                   COALESCE(s.title, m.session_id) AS title,
                   COALESCE(s.project, '') AS project
            FROM messages m
            LEFT JOIN sessions s ON s.session_id=m.session_id
            WHERE m.content LIKE ? COLLATE NOCASE
            ORDER BY m.id DESC LIMIT ?
            """,
            (needle, max(1, min(limit, 200))),
        ).fetchall()
        return [dict(row) for row in rows]

    def fork(self, source_session_id: str, title: str | None = None, copy_last: int = 40) -> SessionInfo:
        source = self.get(source_session_id)
        target = self.create(title or f"{source.title} — fork", project=source.project, channel=source.channel)
        rows = self.db.execute(
            "SELECT role,content,created_at FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?",
            (source_session_id, max(1, min(copy_last, 200))),
        ).fetchall()
        for row in reversed(rows):
            self.db.execute(
                "INSERT INTO messages(session_id,role,content,created_at) VALUES(?,?,?,?)",
                (target.session_id, row["role"], row["content"], row["created_at"]),
            )
        self.db.commit()
        return self.get(target.session_id)

    def close(self) -> None:
        self.db.close()
