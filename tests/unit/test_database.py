import sqlite3
import pytest
from datetime import datetime, timezone


# ── Schema export ─────────────────────────────────────────────────────────

def test_schema_sql_is_importable():
    from backend.db.database import SCHEMA_SQL
    assert "sessions" in SCHEMA_SQL
    assert "events" in SCHEMA_SQL


# ── Session CRUD ──────────────────────────────────────────────────────────

def test_create_session(mem_db):
    from backend.db.database import create_session
    session_id = create_session(mem_db, profile_id="prof-1")
    row = mem_db.execute("SELECT id, profile_id, ended_at FROM sessions WHERE id=?", (session_id,)).fetchone()
    assert row is not None
    assert row[1] == "prof-1"
    assert row[2] is None  # not yet closed


def test_end_session(mem_db):
    from backend.db.database import create_session, end_session
    sid = create_session(mem_db, profile_id="prof-1")
    end_session(mem_db, sid)
    row = mem_db.execute("SELECT ended_at FROM sessions WHERE id=?", (sid,)).fetchone()
    assert row[0] is not None


def test_get_session(mem_db):
    from backend.db.database import create_session, get_session
    sid = create_session(mem_db, profile_id="prof-abc")
    s = get_session(mem_db, sid)
    assert s["id"] == sid
    assert s["profile_id"] == "prof-abc"
    assert s["ended_at"] is None


def test_get_session_not_found(mem_db):
    from backend.db.database import get_session
    assert get_session(mem_db, "nonexistent") is None


# ── Event insert ──────────────────────────────────────────────────────────

def test_insert_event(mem_db):
    from backend.db.database import create_session, insert_event, get_events
    sid = create_session(mem_db, profile_id="prof-1")
    insert_event(mem_db, session_id=sid, profile_id="prof-1", direction="in", occupancy=1)
    events = get_events(mem_db, sid)
    assert len(events) == 1
    assert events[0]["direction"] == "in"
    assert events[0]["occupancy"] == 1


def test_insert_event_direction_constraint(mem_db):
    from backend.db.database import create_session, insert_event
    sid = create_session(mem_db, profile_id="prof-1")
    with pytest.raises(sqlite3.IntegrityError):
        insert_event(mem_db, session_id=sid, profile_id="prof-1", direction="sideways", occupancy=0)


def test_occupancy_floor_constraint(mem_db):
    from backend.db.database import create_session, insert_event
    sid = create_session(mem_db, profile_id="prof-1")
    with pytest.raises(sqlite3.IntegrityError):
        insert_event(mem_db, session_id=sid, profile_id="prof-1", direction="out", occupancy=-1)


# ── Orphan session auto-close ─────────────────────────────────────────────

def test_close_orphaned_sessions(mem_db):
    from backend.db.database import close_orphaned_sessions
    # Manually insert an open session
    mem_db.execute(
        "INSERT INTO sessions (id, profile_id, started_at) VALUES (?,?,?)",
        ("orphan-1", "prof-x", datetime.now(timezone.utc).isoformat()),
    )
    mem_db.commit()
    close_orphaned_sessions(mem_db)
    row = mem_db.execute("SELECT ended_at FROM sessions WHERE id='orphan-1'").fetchone()
    assert row[0] is not None  # must be closed


def test_close_orphaned_sessions_does_not_touch_closed(mem_db):
    from backend.db.database import create_session, end_session, close_orphaned_sessions
    sid = create_session(mem_db, profile_id="prof-1")
    end_session(mem_db, sid)
    original_end = mem_db.execute("SELECT ended_at FROM sessions WHERE id=?", (sid,)).fetchone()[0]
    close_orphaned_sessions(mem_db)
    new_end = mem_db.execute("SELECT ended_at FROM sessions WHERE id=?", (sid,)).fetchone()[0]
    assert original_end == new_end  # unchanged


# ── Sessions list by profile ──────────────────────────────────────────────

def test_list_sessions_for_profile(mem_db):
    from backend.db.database import create_session, end_session, list_sessions_for_profile
    s1 = create_session(mem_db, profile_id="prof-A")
    s2 = create_session(mem_db, profile_id="prof-A")
    end_session(mem_db, s1)
    rows = list_sessions_for_profile(mem_db, "prof-A")
    assert len(rows) == 2
    # newest first
    assert rows[0]["id"] == s2
