from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
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


class ChannelHub:
    """Persistent channel-agnostic message bus.

    External adapters (Telegram, Discord, Slack, email, webhooks, etc.) can map
    messages into this bus without changing SKYNET's conversation core. V0.9
    ships the durable contract first; credentials stay in adapter-specific code.
    """

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=10)
        self.db.row_factory = sqlite3.Row
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
                created_at REAL NOT NULL
            )
            """
        )
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_channel_pending ON channel_messages(direction,status,created_at)")
        self.db.commit()

    @staticmethod
    def _clean(value: str, limit: int) -> str:
        return value.strip()[:limit]

    def receive(self, channel: str, peer: str, content: str, session_id: str) -> ChannelMessage:
        return self._append("inbound", channel, peer, content, session_id, "pending")

    def send(self, channel: str, peer: str, content: str, session_id: str) -> ChannelMessage:
        return self._append("outbound", channel, peer, content, session_id, "queued")

    def _append(self, direction: str, channel: str, peer: str, content: str, session_id: str, status: str) -> ChannelMessage:
        body = content.strip()
        if not body:
            raise ValueError("channel message cannot be empty")
        item = ChannelMessage(
            uuid.uuid4().hex,
            direction,
            self._clean(channel, 64) or "local",
            self._clean(peer, 200),
            self._clean(session_id, 128) or "default",
            body[:200_000],
            status,
            time.time(),
        )
        self.db.execute(
            "INSERT INTO channel_messages(message_id,direction,channel,peer,session_id,content,status,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (item.message_id, item.direction, item.channel, item.peer, item.session_id, item.content, item.status, item.created_at),
        )
        self.db.commit()
        return item

    def pending(self, limit: int = 50) -> list[ChannelMessage]:
        rows = self.db.execute(
            "SELECT * FROM channel_messages WHERE direction='inbound' AND status='pending' ORDER BY created_at LIMIT ?",
            (max(1, min(limit, 500)),),
        ).fetchall()
        return [self._row(r) for r in rows]

    def outbox(self, limit: int = 50) -> list[ChannelMessage]:
        rows = self.db.execute(
            "SELECT * FROM channel_messages WHERE direction='outbound' AND status='queued' ORDER BY created_at LIMIT ?",
            (max(1, min(limit, 500)),),
        ).fetchall()
        return [self._row(r) for r in rows]

    def mark(self, message_id: str, status: str) -> None:
        clean = status.strip()[:64]
        if not clean:
            raise ValueError("status cannot be empty")
        self.db.execute("UPDATE channel_messages SET status=? WHERE message_id=?", (clean, message_id))
        self.db.commit()

    def recent(self, limit: int = 100) -> list[ChannelMessage]:
        rows = self.db.execute("SELECT * FROM channel_messages ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 500)),)).fetchall()
        return [self._row(r) for r in rows]

    @staticmethod
    def _row(row: sqlite3.Row) -> ChannelMessage:
        return ChannelMessage(
            str(row["message_id"]), str(row["direction"]), str(row["channel"]), str(row["peer"]),
            str(row["session_id"]), str(row["content"]), str(row["status"]), float(row["created_at"]),
        )

    def close(self) -> None:
        self.db.close()
