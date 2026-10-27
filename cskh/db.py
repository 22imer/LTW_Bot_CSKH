"""SQLite persistence: users, messages, feedback."""
from __future__ import annotations

import time
from pathlib import Path

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id    INTEGER PRIMARY KEY,
    first_name TEXT,
    username   TEXT,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id, id);
CREATE TABLE IF NOT EXISTS feedback (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    category   TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database is not open")
        return self._conn

    async def open(self) -> None:
        conn = await aiosqlite.connect(self._path)
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.executescript(SCHEMA)
        await conn.commit()
        self._conn = conn

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def upsert_user(
        self, user_id: int, first_name: str | None, username: str | None
    ) -> None:
        await self.conn.execute(
            "INSERT INTO users (user_id, first_name, username, created_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET first_name = excluded.first_name, "
            "username = excluded.username",
            (user_id, first_name, username, time.time()),
        )
        await self.conn.commit()

    async def add_message(self, user_id: int, role: str, content: str) -> None:
        await self.conn.execute(
            "INSERT INTO messages (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (user_id, role, content, time.time()),
        )
        await self.conn.commit()

    async def recent_messages(self, user_id: int, limit: int) -> list[dict[str, str]]:
        """Return the newest `limit` messages, oldest first."""
        async with self.conn.execute(
            "SELECT role, content FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
        return [{"role": role, "content": content} for role, content in reversed(list(rows))]

    async def add_feedback(self, user_id: int, category: str, content: str) -> int:
        cursor = await self.conn.execute(
            "INSERT INTO feedback (user_id, category, content, created_at) VALUES (?, ?, ?, ?)",
            (user_id, category, content, time.time()),
        )
        await self.conn.commit()
        return cursor.lastrowid or 0

    async def purge_messages_older_than(self, days: int) -> int:
        cutoff = time.time() - days * 86400
        cursor = await self.conn.execute("DELETE FROM messages WHERE created_at < ?", (cutoff,))
        await self.conn.commit()
        return cursor.rowcount
