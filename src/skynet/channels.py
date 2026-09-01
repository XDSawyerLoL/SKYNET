from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
import threading
import time
import uuid


@dataclass(frozen=True, slots=True)
class ChannelMessage:
    message_id: str
    direction: str
    channel: str
    peer: str
    session_id: str
    content: str
    status: str
    created_at: float
    dedupe_key: str | None = None


class ChannelHub:
    """Persistent channel-agnostic message bus with idempotent delivery.

    External adapters can supply a stable ``dedupe_key`` (for example a
    Telegram update id, Discord event id or webhook event id). Retries with the
    same key return the original message instead of duplicating a side effect.
    """

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, timeout=10, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        with self.lock:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS channel_messages (
                    message_id TEXT PRIMARY KEY,
                    direction TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    peer TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    dedupe_key TEXT
                )
                """
            )
            columns = {str(row[1]) for row in self.db.execute("PRAGMA table_info(channel_messages)").fetchall()}
            if "dedupe_key" not in columns:
                self.db.execute("ALTER TABLE channel_messages ADD COLUMN dedupe_key TEXT")
            self.db.execute("CREATE INDEX IF NOT EXISTS idx_channel_pending ON channel_messages(direction,status,created_at)")
            self.db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_channel_dedupe "
                "ON channel_messages(direction,channel,peer,dedupe_key) WHERE dedupe_key IS NOT NULL"
            )
            self.db.commit()

    @staticmethod
    def _clean(value: str, limit: int) -> str:
        return value.strip()[:limit]

    def receive(self, channel: str, peer: str, content: str, session_id: str, dedupe_key: str | None = None) -> ChannelMessage:
        return self._append("inbound", channel, peer, content, session_id, "pending", dedupe_key)

    def send(self, channel: str, peer: str, content: str, session_id: str, dedupe_key: str | None = None) -> ChannelMessage:
        return self._append("outbound", channel, peer, content, session_id, "queued", dedupe_key)

    def _append(
        self,
        direction: str,
        channel: str,
        peer: str,
        content: str,
        session_id: str,
        status: str,
        dedupe_key: str | None,
    ) -> ChannelMessage:
        body = content.strip()
        if not body:
            raise ValueError("channel message cannot be empty")
        clean_channel = self._clean(channel, 64) or "local"
        clean_peer = self._clean(peer, 200)
        clean_session = self._clean(session_id, 128) or "default"
        clean_dedupe = None if dedupe_key is None else self._clean(str(dedupe_key), 300)
        if clean_dedupe == "":
            clean_dedupe = None
        with self.lock:
            if clean_dedupe is not None:
                existing = self.db.execute(
                    "SELECT * FROM channel_messages WHERE direction=? AND channel=? AND peer=? AND dedupe_key=?",
                    (direction, clean_channel, clean_peer, clean_dedupe),
                ).fetchone()
                if existing is not None:
                    return self._row(existing)
            item = ChannelMessage(
                uuid.uuid4().hex,
                direction,
                clean_channel,
                clean_peer,
                clean_session,
                body[:200_000],
                status,
                time.time(),
                clean_dedupe,
            )
            try:
                self.db.execute(
                    "INSERT INTO channel_messages(message_id,direction,channel,peer,session_id,content,status,created_at,dedupe_key) "
                    "VALUES(?,?,?,?,?,?,?,?,?)",
                    (item.message_id, item.direction, item.channel, item.peer, item.session_id, item.content,
                     item.status, item.created_at, item.dedupe_key),
                )
                self.db.commit()
                return item
            except sqlite3.IntegrityError:
                if clean_dedupe is None:
                    raise
                existing = self.db.execute(
                    "SELECT * FROM channel_messages WHERE direction=? AND channel=? AND peer=? AND dedupe_key=?",
                    (direction, clean_channel, clean_peer, clean_dedupe),
                ).fetchone()
                if existing is None:
                    raise
                return self._row(existing)

    def pending(self, limit: int = 50) -> list[ChannelMessage]:
        with self.lock:
            rows = self.db.execute(
                "SELECT * FROM channel_messages WHERE direction='inbound' AND status='pending' ORDER BY created_at LIMIT ?",
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [self._row(r) for r in rows]

    def outbox(self, limit: int = 50) -> list[ChannelMessage]:
        with self.lock:
            rows = self.db.execute(
                "SELECT * FROM channel_messages WHERE direction='outbound' AND status='queued' ORDER BY created_at LIMIT ?",
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [self._row(r) for r in rows]

    def mark(self, message_id: str, status: str) -> None:
        clean = status.strip()[:64]
        if not clean:
            raise ValueError("status cannot be empty")
        with self.lock:
            self.db.execute("UPDATE channel_messages SET status=? WHERE message_id=?", (clean, message_id))
            self.db.commit()

    def recent(self, limit: int = 100) -> list[ChannelMessage]:
        with self.lock:
            rows = self.db.execute(
                "SELECT * FROM channel_messages ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 500)),)
            ).fetchall()
        return [self._row(r) for r in rows]

    @staticmethod
    def _row(row: sqlite3.Row) -> ChannelMessage:
        keys = set(row.keys())
        return ChannelMessage(
            str(row["message_id"]), str(row["direction"]), str(row["channel"]), str(row["peer"]),
            str(row["session_id"]), str(row["content"]), str(row["status"]), float(row["created_at"]),
            None if "dedupe_key" not in keys or row["dedupe_key"] is None else str(row["dedupe_key"]),
        )

    def close(self) -> None:
        with self.lock:
            self.db.close()
