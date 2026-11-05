"""SQLite persistence for channels, threads, messages and session associations.

No credential is ever written here; tests scan the file for the configured secrets.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

USERS: tuple[tuple[str, str, str], ...] = (
    ("ava", "Ava Ramirez", "#7c3aed"),
    ("ben", "Ben Okafor", "#0891b2"),
    ("chloe", "Chloe Nguyen", "#db2777"),
    ("dev", "Dev Patel", "#ea580c"),
    ("elena", "Elena Rossi", "#16a34a"),
)
BOT_HANDLE = "devin"
BOT_NAME = "Devin"
CHANNELS: tuple[tuple[str, str], ...] = (
    ("general", "Team-wide chatter"),
    ("collection-ops", "Collection jobs, data loads and dashboards"),
    ("alerts", "Synthetic alert feed"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    handle TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    color TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    topic TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS threads (
    id INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL REFERENCES channels(id),
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    thread_id INTEGER NOT NULL REFERENCES threads(id),
    author_kind TEXT NOT NULL CHECK (author_kind IN ('user', 'devin', 'system')),
    author_handle TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at REAL NOT NULL,
    client_msg_id TEXT,
    devin_event_id TEXT,
    forward_state TEXT NOT NULL DEFAULT 'none',
    UNIQUE (thread_id, client_msg_id),
    UNIQUE (thread_id, devin_event_id)
);
CREATE INDEX IF NOT EXISTS messages_thread ON messages(thread_id, id);
CREATE TABLE IF NOT EXISTS thread_sessions (
    thread_id INTEGER PRIMARY KEY REFERENCES threads(id),
    state TEXT NOT NULL,
    session_id TEXT UNIQUE,
    session_url TEXT,
    initial_message_id INTEGER,
    last_cursor TEXT,
    detail TEXT,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS dispatches (
    message_id INTEGER PRIMARY KEY REFERENCES messages(id),
    route TEXT NOT NULL CHECK (route IN ('direct', 'automation', 'forward')),
    state TEXT NOT NULL,
    detail TEXT,
    updated_at REAL NOT NULL
);
"""

RECLAIMABLE = ("failed", "interrupted")


class Store:
    def __init__(self, path: str) -> None:
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None, timeout=10)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA)
        with self.tx() as c:
            c.executemany("INSERT OR IGNORE INTO users VALUES (?, ?, ?)", USERS)
            c.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?)", (BOT_HANDLE, BOT_NAME, "#111827"))
            c.executemany("INSERT OR IGNORE INTO channels(name, topic) VALUES (?, ?)", CHANNELS)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            self._conn.execute("COMMIT")

    def query(self, sql: str, args: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._conn.execute(sql, args).fetchall())

    def one(self, sql: str, args: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        rows = self.query(sql, args)
        return rows[0] if rows else None

    # ---- reads -------------------------------------------------------------
    def users(self) -> list[dict[str, str]]:
        return [
            {"handle": r["handle"], "name": r["display_name"], "color": r["color"], "bot": r["handle"] == BOT_HANDLE}
            for r in self.query("SELECT * FROM users ORDER BY handle = ?, display_name", (BOT_HANDLE,))
        ]

    def human_handles(self) -> set[str]:
        return {u[0] for u in USERS}

    def display_name(self, handle: str) -> str:
        row = self.one("SELECT display_name FROM users WHERE handle = ?", (handle,))
        return row["display_name"] if row else handle

    def channels(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.query("SELECT id, name, topic FROM channels ORDER BY id")]

    def channel(self, channel_id: int) -> sqlite3.Row | None:
        return self.one("SELECT * FROM channels WHERE id = ?", (channel_id,))

    def thread(self, thread_id: int) -> sqlite3.Row | None:
        return self.one("SELECT * FROM threads WHERE id = ?", (thread_id,))

    def session_for(self, thread_id: int) -> sqlite3.Row | None:
        return self.one("SELECT * FROM thread_sessions WHERE thread_id = ?", (thread_id,))

    def thread_summaries(self, channel_id: int) -> list[dict[str, Any]]:
        rows = self.query(
            """
            SELECT t.id, t.created_at,
                   (SELECT m.id FROM messages m WHERE m.thread_id = t.id ORDER BY m.id LIMIT 1) AS root_id,
                   (SELECT COUNT(*) - 1 FROM messages m WHERE m.thread_id = t.id) AS replies,
                   (SELECT MAX(m.created_at) FROM messages m WHERE m.thread_id = t.id) AS last_at,
                   s.state AS session_state
            FROM threads t LEFT JOIN thread_sessions s ON s.thread_id = t.id
            WHERE t.channel_id = ? ORDER BY last_at DESC LIMIT 200
            """,
            (channel_id,),
        )
        out = []
        for r in rows:
            root = self.message(r["root_id"]) if r["root_id"] else None
            out.append(
                {
                    "id": r["id"],
                    "replies": max(0, r["replies"]),
                    "last_at": r["last_at"],
                    "session_state": r["session_state"],
                    "root": root,
                }
            )
        return out

    def message(self, message_id: int) -> dict[str, Any] | None:
        r = self.one("SELECT * FROM messages WHERE id = ?", (message_id,))
        return _public_message(r) if r else None

    def messages(self, thread_id: int, after_id: int = 0) -> list[dict[str, Any]]:
        rows = self.query("SELECT * FROM messages WHERE thread_id = ? AND id > ? ORDER BY id LIMIT 500", (thread_id, after_id))
        return [_public_message(r) for r in rows]

    # ---- writes ------------------------------------------------------------
    def create_thread(self, channel_id: int, author: str, body: str, client_msg_id: str) -> tuple[int, int, bool]:
        """Returns (thread_id, message_id, created). Replaying a client_msg_id returns the original."""
        with self.tx() as c:
            prior = c.execute(
                """SELECT m.thread_id, m.id FROM messages m JOIN threads t ON t.id = m.thread_id
                   WHERE t.channel_id = ? AND m.client_msg_id = ? AND m.author_handle = ?""",
                (channel_id, client_msg_id, author),
            ).fetchone()
            if prior:
                return prior["thread_id"], prior["id"], False
            now = time.time()
            tid = c.execute("INSERT INTO threads(channel_id, created_at) VALUES (?, ?)", (channel_id, now)).lastrowid
            mid = c.execute(
                """INSERT INTO messages(thread_id, author_kind, author_handle, body, created_at, client_msg_id)
                   VALUES (?, 'user', ?, ?, ?, ?)""",
                (tid, author, body, now, client_msg_id),
            ).lastrowid
            assert tid is not None and mid is not None
            return tid, mid, True

    def add_user_message(self, thread_id: int, author: str, body: str, client_msg_id: str) -> tuple[int, bool]:
        with self.tx() as c:
            prior = c.execute(
                "SELECT id FROM messages WHERE thread_id = ? AND client_msg_id = ?", (thread_id, client_msg_id)
            ).fetchone()
            if prior:
                return prior["id"], False
            mid = c.execute(
                """INSERT INTO messages(thread_id, author_kind, author_handle, body, created_at, client_msg_id)
                   VALUES (?, 'user', ?, ?, ?, ?)""",
                (thread_id, author, body, time.time(), client_msg_id),
            ).lastrowid
            assert mid is not None
            return mid, True

    def add_system_message(self, thread_id: int, body: str) -> int:
        with self.tx() as c:
            mid = c.execute(
                """INSERT INTO messages(thread_id, author_kind, author_handle, body, created_at)
                   VALUES (?, 'system', 'system', ?, ?)""",
                (thread_id, body, time.time()),
            ).lastrowid
            assert mid is not None
            return mid

    def add_devin_message(self, thread_id: int, event_id: str, body: str) -> bool:
        with self.tx() as c:
            cur = c.execute(
                """INSERT OR IGNORE INTO messages(thread_id, author_kind, author_handle, body, created_at, devin_event_id)
                   VALUES (?, 'devin', ?, ?, ?, ?)""",
                (thread_id, BOT_HANDLE, body, time.time(), event_id),
            )
            return cur.rowcount == 1

    def claim_dispatch(self, message_id: int, route: str) -> bool:
        with self.tx() as c:
            cur = c.execute(
                "INSERT OR IGNORE INTO dispatches(message_id, route, state, updated_at) VALUES (?, ?, 'pending', ?)",
                (message_id, route, time.time()),
            )
            return cur.rowcount == 1

    def set_dispatch(self, message_id: int, state: str, detail: str | None = None) -> None:
        with self.tx() as c:
            c.execute(
                "UPDATE dispatches SET state = ?, detail = ?, updated_at = ? WHERE message_id = ?",
                (state, detail, time.time(), message_id),
            )

    def claim_session(self, thread_id: int, initial_message_id: int) -> bool:
        """Atomically claim the right to create the one session for this thread."""
        with self.tx() as c:
            cur = c.execute(
                """INSERT INTO thread_sessions(thread_id, state, initial_message_id, updated_at)
                   VALUES (?, 'creating', ?, ?)
                   ON CONFLICT(thread_id) DO UPDATE SET state = 'creating', session_id = NULL,
                       session_url = NULL, initial_message_id = excluded.initial_message_id,
                       last_cursor = NULL, detail = NULL, updated_at = excluded.updated_at
                   WHERE thread_sessions.state IN ('failed', 'interrupted')""",
                (thread_id, initial_message_id, time.time()),
            )
            return cur.rowcount == 1

    def update_session(self, thread_id: int, **fields: Any) -> None:
        allowed = {"state", "session_id", "session_url", "last_cursor", "detail"}
        if not fields or not set(fields) <= allowed:
            raise ValueError("bad session fields")
        cols = ", ".join(f"{k} = ?" for k in fields)
        with self.tx() as c:
            c.execute(
                f"UPDATE thread_sessions SET {cols}, updated_at = ? WHERE thread_id = ?",  # noqa: S608 - fixed keys
                (*fields.values(), time.time(), thread_id),
            )

    def set_forward_state(self, message_id: int, state: str) -> None:
        with self.tx() as c:
            c.execute("UPDATE messages SET forward_state = ? WHERE id = ?", (state, message_id))

    def pending_forwards(self, thread_id: int) -> list[sqlite3.Row]:
        return self.query("SELECT * FROM messages WHERE thread_id = ? AND forward_state = 'pending' ORDER BY id", (thread_id,))

    def threads_with_state(self, *states: str) -> list[sqlite3.Row]:
        marks = ",".join("?" for _ in states)
        return self.query(f"SELECT * FROM thread_sessions WHERE state IN ({marks})", states)  # noqa: S608

    def threads_with_pending(self) -> list[int]:
        return [r[0] for r in self.query("SELECT DISTINCT thread_id FROM messages WHERE forward_state = 'pending'")]

    def pending_automation(self) -> list[int]:
        return [r[0] for r in self.query("SELECT message_id FROM dispatches WHERE route = 'automation' AND state = 'pending'")]


def _public_message(r: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": r["id"],
        "thread_id": r["thread_id"],
        "kind": r["author_kind"],
        "author": r["author_handle"],
        "body": r["body"],
        "created_at": r["created_at"],
        "forward_state": r["forward_state"],
    }
