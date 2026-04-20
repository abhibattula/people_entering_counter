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
    """Create a session and return its ID."""
    resp = await api_client.post("/api/sessions/start", json={"profile_id": "test-profile-1"})
    assert resp.status_code == 201
    return resp.json()["session_id"]


# ── POST /api/sessions/start ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_session_returns_201(api_client):
    resp = await api_client.post("/api/sessions/start", json={"profile_id": "test-profile-2"})
    assert resp.status_code == 201
    body = resp.json()
    assert "session_id" in body
    assert "started_at" in body


@pytest.mark.asyncio
async def test_start_session_body_fields(api_client):
    resp = await api_client.post("/api/sessions/start", json={"profile_id": "test-profile-3"})
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
    profile_id = "unique-profile-for-listing"
    start_resp = await api_client.post("/api/sessions/start", json={"profile_id": profile_id})
    created_id = start_resp.json()["session_id"]

    resp = await api_client.get(f"/api/sessions?profile_id={profile_id}")
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert created_id in ids


@pytest.mark.asyncio
async def test_list_sessions_empty_for_unknown_profile(api_client):
    resp = await api_client.get("/api/sessions?profile_id=totally-unknown-profile-xyz")
    assert resp.status_code == 200
    assert resp.json() == []
