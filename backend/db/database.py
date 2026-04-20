import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.config import DB_PATH

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    started_at DATETIME NOT NULL,
    ended_at   DATETIME
);

CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    profile_id TEXT NOT NULL,
    timestamp  DATETIME NOT NULL,
    direction  TEXT NOT NULL CHECK(direction IN ('in', 'out')),
    occupancy  INTEGER NOT NULL CHECK(occupancy >= 0)
);

CREATE INDEX IF NOT EXISTS idx_events_session   ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    close_orphaned_sessions(conn)
    return conn


# ── Session operations ────────────────────────────────────────────────────


def create_session(conn: sqlite3.Connection, profile_id: str) -> str:
    session_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO sessions (id, profile_id, started_at) VALUES (?, ?, ?)",
        (session_id, profile_id, _now()),
    )
    conn.commit()
    return session_id


def end_session(conn: sqlite3.Connection, session_id: str) -> None:
    conn.execute(
        "UPDATE sessions SET ended_at=? WHERE id=?",
        (_now(), session_id),
    )
    conn.commit()


def get_session(conn: sqlite3.Connection, session_id: str) -> Optional[dict]:
    row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    return dict(row) if row else None


def list_sessions_for_profile(conn: sqlite3.Connection, profile_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT s.id, s.profile_id, s.started_at, s.ended_at,
               COUNT(CASE WHEN e.direction='in'  THEN 1 END) AS total_in,
               COUNT(CASE WHEN e.direction='out' THEN 1 END) AS total_out
        FROM sessions s
        LEFT JOIN events e ON e.session_id = s.id
        WHERE s.profile_id=?
        GROUP BY s.id
        ORDER BY s.rowid DESC
        """,
        (profile_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def close_orphaned_sessions(conn: sqlite3.Connection) -> None:
    conn.execute(
        "UPDATE sessions SET ended_at=? WHERE ended_at IS NULL",
        (_now(),),
    )
    conn.commit()


# ── Event operations ──────────────────────────────────────────────────────


def insert_event(
    conn: sqlite3.Connection,
    session_id: str,
    profile_id: str,
    direction: str,
    occupancy: int,
) -> None:
    conn.execute(
        "INSERT INTO events (session_id, profile_id, timestamp, direction, occupancy) VALUES (?,?,?,?,?)",
        (session_id, profile_id, _now(), direction, occupancy),
    )
    conn.commit()


def get_events(conn: sqlite3.Connection, session_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM events WHERE session_id=? ORDER BY timestamp ASC",
        (session_id,),
    ).fetchall()
    return [dict(r) for r in rows]
