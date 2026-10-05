"""SQLite storage for accounts, sessions and room snapshots.

Live room state is kept in memory by the RoomManager; the rooms table holds a
JSON snapshot so rooms survive a server restart.
"""

import json
import sqlite3
import threading
import time

from . import config

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS rooms (
    id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
"""


def conn() -> sqlite3.Connection:
    c = getattr(_local, "conn", None)
    if c is None:
        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        c.execute("PRAGMA journal_mode = WAL")
        c.executescript(SCHEMA)
        _local.conn = c
    return c


def reset_connection() -> None:
    c = getattr(_local, "conn", None)
    if c is not None:
        c.close()
        _local.conn = None


# ---- users -----------------------------------------------------------------

def create_user(username: str, password_hash: str) -> int:
    with conn() as c:
        cur = c.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username, password_hash, time.time()),
        )
        return cur.lastrowid


def get_user_by_name(username: str) -> sqlite3.Row | None:
    return conn().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def get_user(user_id: int) -> sqlite3.Row | None:
    return conn().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def create_session(token: str, user_id: int) -> None:
    with conn() as c:
        c.execute(
            "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
            (token, user_id, time.time()),
        )


def user_for_token(token: str) -> sqlite3.Row | None:
    return conn().execute(
        "SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id WHERE token = ?",
        (token,),
    ).fetchone()


def delete_session(token: str) -> None:
    with conn() as c:
        c.execute("DELETE FROM sessions WHERE token = ?", (token,))


# ---- rooms -----------------------------------------------------------------

def room_exists(room_id: str) -> bool:
    return conn().execute("SELECT 1 FROM rooms WHERE id = ?", (room_id,)).fetchone() is not None


def save_room(room_id: str, data: dict) -> None:
    now = time.time()
    with conn() as c:
        c.execute(
            """INSERT INTO rooms (id, data, created_at, updated_at) VALUES (?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at""",
            (room_id, json.dumps(data), now, now),
        )


def load_room(room_id: str) -> dict | None:
    row = conn().execute("SELECT data FROM rooms WHERE id = ?", (room_id,)).fetchone()
    return json.loads(row["data"]) if row else None


def delete_room(room_id: str) -> None:
    with conn() as c:
        c.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
