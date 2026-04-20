import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel

from backend.db.database import (
    get_connection,
    create_session,
    end_session,
    get_session,
    get_events,
    list_sessions_for_profile,
)

router = APIRouter()

# Track paused sessions
_paused_sessions: set[str] = set()


class StartSessionRequest(BaseModel):
    profile_id: str


@router.post("/sessions/start", status_code=201)
def start_session(body: StartSessionRequest):
    conn = get_connection()
    try:
        # Check for an already-active session for this profile (spec §229)
        active = conn.execute(
            "SELECT id FROM sessions WHERE profile_id=? AND ended_at IS NULL LIMIT 1",
            (body.profile_id,),
        ).fetchone()
        if active:
            raise HTTPException(409, detail="A session for this profile is already active")
        session_id = create_session(conn, body.profile_id)
        session = get_session(conn, session_id)
        return {"session_id": session_id, "started_at": session["started_at"]}
    finally:
        conn.close()


@router.post("/sessions/{session_id}/end", status_code=204)
def end_session_route(session_id: str):
    conn = get_connection()
    try:
        session = get_session(conn, session_id)
        if not session:
            raise HTTPException(404, detail="Session not found")
        end_session(conn, session_id)
        _paused_sessions.discard(session_id)
    finally:
        conn.close()
    return Response(status_code=204)


@router.post("/sessions/{session_id}/pause", status_code=204)
def pause_session(session_id: str):
    conn = get_connection()
    try:
        session = get_session(conn, session_id)
        if not session:
            raise HTTPException(404, detail="Session not found")
        if session["ended_at"] is not None:
            raise HTTPException(409, detail="Session is already ended")
        if session_id in _paused_sessions:
            raise HTTPException(409, detail="Session is already paused")
        _paused_sessions.add(session_id)

        # Pause the counting service if running
        from backend.services.counting_service import get_or_create_service
        try:
            svc = get_or_create_service(session["profile_id"])
            svc.pause()
        except Exception:
            pass
    finally:
        conn.close()
    return Response(status_code=204)


@router.post("/sessions/{session_id}/resume", status_code=204)
def resume_session(session_id: str):
    conn = get_connection()
    try:
        session = get_session(conn, session_id)
        if not session:
            raise HTTPException(404, detail="Session not found")
        if session_id not in _paused_sessions:
            raise HTTPException(409, detail="Session is not paused")
        _paused_sessions.discard(session_id)

        from backend.services.counting_service import get_or_create_service
        try:
            svc = get_or_create_service(session["profile_id"])
            svc.resume()
        except Exception:
            pass
    finally:
        conn.close()
    return Response(status_code=204)


@router.get("/sessions/{session_id}/events")
def get_session_events(session_id: str):
    conn = get_connection()
    try:
        session = get_session(conn, session_id)
        if not session:
            raise HTTPException(404, detail="Session not found")
        events = get_events(conn, session_id)
        return [
            {
                "id": e["id"],
                "timestamp": e["timestamp"],
                "direction": e["direction"],
                "occupancy": e["occupancy"],
            }
            for e in events
        ]
    finally:
        conn.close()


@router.get("/sessions/{session_id}/export")
def export_session_csv(session_id: str):
    conn = get_connection()
    try:
        session = get_session(conn, session_id)
        if not session:
            raise HTTPException(404, detail="Session not found")
        events = get_events(conn, session_id)
    finally:
        conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "timestamp", "direction", "occupancy"])
    for e in events:
        writer.writerow([e["id"], e["timestamp"], e["direction"], e["occupancy"]])
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="session-{session_id}.csv"'},
    )


@router.get("/sessions")
def list_sessions(profile_id: str):
    conn = get_connection()
    try:
        rows = list_sessions_for_profile(conn, profile_id)
        return rows
    finally:
        conn.close()
