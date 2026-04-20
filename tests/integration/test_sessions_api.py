import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch


@pytest_asyncio.fixture()
async def api_client():
    from backend.main import app
    # Patch close_orphaned_sessions so it does not auto-end sessions that were
    # just created within the same test. The real DB path is used (same as other
    # integration tests), but orphan-closing would end our freshly-created
    # sessions on every subsequent get_connection() call.
    with patch("backend.db.database.close_orphaned_sessions"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


@pytest_asyncio.fixture()
async def session_id(api_client):
    """Create a session and return its ID. Uses a unique profile per call to avoid 409 conflicts."""
    unique_profile = f"test-profile-{uuid.uuid4().hex[:8]}"
    resp = await api_client.post("/api/sessions/start", json={"profile_id": unique_profile})
    assert resp.status_code == 201
    return resp.json()["session_id"]


def _clear_paused_sessions():
    """Clear the module-level _paused_sessions set to avoid cross-test pollution."""
    from backend.routers import sessions as sessions_router
    sessions_router._paused_sessions.clear()


# ── POST /api/sessions/start ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_session_returns_201(api_client):
    resp = await api_client.post("/api/sessions/start", json={"profile_id": f"test-profile-{uuid.uuid4().hex[:8]}"})
    assert resp.status_code == 201
    body = resp.json()
    assert "session_id" in body
    assert "started_at" in body


@pytest.mark.asyncio
async def test_start_session_body_fields(api_client):
    resp = await api_client.post("/api/sessions/start", json={"profile_id": f"test-profile-{uuid.uuid4().hex[:8]}"})
    body = resp.json()
    # session_id should be a non-empty string (UUID)
    assert isinstance(body["session_id"], str)
    assert len(body["session_id"]) > 0
    # started_at should be a non-empty string (ISO timestamp)
    assert isinstance(body["started_at"], str)
    assert len(body["started_at"]) > 0


# ── POST /api/sessions/{id}/end ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_end_session_returns_204(api_client, session_id):
    resp = await api_client.post(f"/api/sessions/{session_id}/end")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_end_nonexistent_session_returns_404(api_client):
    resp = await api_client.post("/api/sessions/nonexistent-session-id/end")
    assert resp.status_code == 404


# ── POST /api/sessions/{id}/pause ────────────────────────────────────────


@pytest.mark.asyncio
async def test_pause_session_returns_204(api_client, session_id):
    resp = await api_client.post(f"/api/sessions/{session_id}/pause")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_pause_nonexistent_session_returns_404(api_client):
    resp = await api_client.post("/api/sessions/nonexistent-session-id/pause")
    assert resp.status_code == 404


# ── POST /api/sessions/{id}/resume ───────────────────────────────────────


@pytest.mark.asyncio
async def test_resume_session_returns_204(api_client, session_id):
    # Must pause first before resuming
    await api_client.post(f"/api/sessions/{session_id}/pause")
    resp = await api_client.post(f"/api/sessions/{session_id}/resume")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_resume_nonexistent_session_returns_404(api_client):
    resp = await api_client.post("/api/sessions/nonexistent-session-id/resume")
    assert resp.status_code == 404


# ── GET /api/sessions/{id}/events ────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_events_returns_200_empty_list(api_client, session_id):
    resp = await api_client.get(f"/api/sessions/{session_id}/events")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 0


@pytest.mark.asyncio
async def test_get_events_nonexistent_session_returns_404(api_client):
    resp = await api_client.get("/api/sessions/nonexistent-session-id/events")
    assert resp.status_code == 404


# ── GET /api/sessions/{id}/export ────────────────────────────────────────


@pytest.mark.asyncio
async def test_export_session_csv_returns_200(api_client, session_id):
    resp = await api_client.get(f"/api/sessions/{session_id}/export")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_export_session_csv_content_disposition(api_client, session_id):
    resp = await api_client.get(f"/api/sessions/{session_id}/export")
    content_disposition = resp.headers.get("content-disposition", "")
    assert "attachment" in content_disposition
    assert "filename=" in content_disposition
    assert f"session-{session_id}" in content_disposition


@pytest.mark.asyncio
async def test_export_session_csv_has_header_row(api_client, session_id):
    resp = await api_client.get(f"/api/sessions/{session_id}/export")
    text = resp.text
    # CSV should have the header row
    assert "id" in text
    assert "timestamp" in text
    assert "direction" in text
    assert "occupancy" in text


@pytest.mark.asyncio
async def test_export_nonexistent_session_returns_404(api_client):
    resp = await api_client.get("/api/sessions/nonexistent-session-id/export")
    assert resp.status_code == 404


# ── GET /api/sessions?profile_id=xxx ─────────────────────────────────────


@pytest.mark.asyncio
async def test_list_sessions_returns_200(api_client):
    resp = await api_client.get("/api/sessions?profile_id=some-profile")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_sessions_includes_created_session(api_client):
    profile_id = f"unique-profile-for-listing-{uuid.uuid4().hex[:8]}"
    start_resp = await api_client.post("/api/sessions/start", json={"profile_id": profile_id})
    created_id = start_resp.json()["session_id"]

    resp = await api_client.get(f"/api/sessions?profile_id={profile_id}")
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert created_id in ids


@pytest.mark.asyncio
async def test_list_sessions_item_schema(api_client):
    profile_id = f"profile-for-schema-check-{uuid.uuid4().hex[:8]}"
    await api_client.post("/api/sessions/start", json={"profile_id": profile_id})

    resp = await api_client.get(f"/api/sessions?profile_id={profile_id}")
    assert resp.status_code == 200
    sessions = resp.json()
    assert len(sessions) >= 1
    item = sessions[0]
    for key in ("started_at", "ended_at", "total_in", "total_out"):
        assert key in item, f"Expected key '{key}' missing from session list item"


@pytest.mark.asyncio
async def test_list_sessions_empty_for_unknown_profile(api_client):
    resp = await api_client.get("/api/sessions?profile_id=totally-unknown-profile-xyz")
    assert resp.status_code == 200
    assert resp.json() == []


# ── GET /api/sessions — 422 when profile_id missing ──────────────────────


@pytest.mark.asyncio
async def test_list_sessions_missing_profile_id_returns_422(api_client):
    resp = await api_client.get("/api/sessions")
    assert resp.status_code == 422


# ── GET /api/sessions/{id}/events — populated list schema ────────────────


@pytest.mark.asyncio
async def test_get_events_populated_list_schema(api_client):
    profile_id = f"profile-for-events-schema-{uuid.uuid4().hex[:8]}"
    with patch("backend.db.database.close_orphaned_sessions"):
        start_resp = await api_client.post("/api/sessions/start", json={"profile_id": profile_id})
    assert start_resp.status_code == 201
    sid = start_resp.json()["session_id"]

    # Insert a crossing event directly into the same DB the API uses
    from backend.db.database import get_connection, insert_event
    with patch("backend.db.database.close_orphaned_sessions"):
        conn = get_connection()
    try:
        insert_event(conn, sid, profile_id, "in", 1)
    finally:
        conn.close()

    resp = await api_client.get(f"/api/sessions/{sid}/events")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) >= 1
    event = events[0]
    for key in ("id", "timestamp", "direction", "occupancy"):
        assert key in event, f"Expected key '{key}' missing from event item"


# ── 409 conflict tests ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_session_conflict_returns_409(api_client):
    """Starting a second active session for the same profile returns 409."""
    profile_id = f"conflict-profile-start-{uuid.uuid4().hex[:8]}"
    resp1 = await api_client.post("/api/sessions/start", json={"profile_id": profile_id})
    assert resp1.status_code == 201

    resp2 = await api_client.post("/api/sessions/start", json={"profile_id": profile_id})
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_pause_already_ended_session_returns_409(api_client):
    """Pausing an already-ended session returns 409."""
    _clear_paused_sessions()
    profile_id = f"conflict-profile-pause-ended-{uuid.uuid4().hex[:8]}"
    start_resp = await api_client.post("/api/sessions/start", json={"profile_id": profile_id})
    assert start_resp.status_code == 201
    sid = start_resp.json()["session_id"]

    end_resp = await api_client.post(f"/api/sessions/{sid}/end")
    assert end_resp.status_code == 204

    pause_resp = await api_client.post(f"/api/sessions/{sid}/pause")
    assert pause_resp.status_code == 409


@pytest.mark.asyncio
async def test_resume_when_not_paused_returns_409(api_client):
    """Resuming a session that was never paused returns 409."""
    _clear_paused_sessions()
    profile_id = f"conflict-profile-resume-not-paused-{uuid.uuid4().hex[:8]}"
    start_resp = await api_client.post("/api/sessions/start", json={"profile_id": profile_id})
    assert start_resp.status_code == 201
    sid = start_resp.json()["session_id"]

    resume_resp = await api_client.post(f"/api/sessions/{sid}/resume")
    assert resume_resp.status_code == 409
