import json
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


VALID_PROFILE = {
    "name": "Test Entrance",
    "camera_index": 0,
    "capture_mode": "photo",
    "frame_width": 1280,
    "frame_height": 720,
    "roi_polygon": [[210,40],[430,40],[430,320],[210,320]],
    "counting_line": {"x1": 210, "y1": 180, "x2": 430, "y2": 180},
    "inside_direction": "up",
    "door_randomly_opens": False,
    "quality_check": {
        "door_fully_visible": True,
        "lighting_acceptable": True,
        "crowding_risk": "low",
        "camera_adjustment": "keep",
    },
}


@pytest_asyncio.fixture()
async def api_client():
    from backend.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_create_profile_returns_201(api_client):
    resp = await api_client.post("/api/profiles", json=VALID_PROFILE)
    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    assert "created_at" in body


@pytest.mark.asyncio
async def test_list_profiles_returns_200(api_client):
    resp = await api_client.get("/api/profiles")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_profiles_includes_created_profile(api_client):
    await api_client.post("/api/profiles", json=VALID_PROFILE)
    resp = await api_client.get("/api/profiles")
    names = [p["name"] for p in resp.json()]
    assert "Test Entrance" in names


@pytest.mark.asyncio
async def test_get_profile_by_id(api_client):
    created = (await api_client.post("/api/profiles", json=VALID_PROFILE)).json()
    resp = await api_client.get(f"/api/profiles/{created['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == created["id"]
    assert body["name"] == "Test Entrance"
    assert body["roi_polygon"] == VALID_PROFILE["roi_polygon"]


@pytest.mark.asyncio
async def test_get_profile_not_found(api_client):
    resp = await api_client.get("/api/profiles/nonexistent-uuid")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_profile_returns_204(api_client):
    created = (await api_client.post("/api/profiles", json=VALID_PROFILE)).json()
    resp = await api_client.delete(f"/api/profiles/{created['id']}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_get_deleted_profile_returns_404(api_client):
    created = (await api_client.post("/api/profiles", json=VALID_PROFILE)).json()
    await api_client.delete(f"/api/profiles/{created['id']}")
    resp = await api_client.get(f"/api/profiles/{created['id']}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_profile_validates_name_empty(api_client):
    bad = {**VALID_PROFILE, "name": ""}
    resp = await api_client.post("/api/profiles", json=bad)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_profile_validates_invalid_direction(api_client):
    bad = {**VALID_PROFILE, "inside_direction": "diagonal"}
    resp = await api_client.post("/api/profiles", json=bad)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_export_profile_returns_json_file(api_client):
    created = (await api_client.post("/api/profiles", json=VALID_PROFILE)).json()
    resp = await api_client.get(f"/api/profiles/{created['id']}/export")
    assert resp.status_code == 200
    assert "attachment" in resp.headers.get("content-disposition", "")
    body = resp.json()
    assert body["id"] == created["id"]


@pytest.mark.asyncio
async def test_import_profile_assigns_new_id(api_client):
    created = (await api_client.post("/api/profiles", json=VALID_PROFILE)).json()
    export_resp = await api_client.get(f"/api/profiles/{created['id']}/export")
    profile_json = export_resp.content

    import_resp = await api_client.post(
        "/api/profiles/import",
        files=[("file", ("profile.json", profile_json, "application/json"))],
    )
    assert import_resp.status_code == 201
    new_body = import_resp.json()
    assert new_body["id"] != created["id"]  # new UUID assigned


@pytest.mark.asyncio
async def test_list_profiles_has_stats_fields(api_client):
    """GET /api/profiles must include total_in, total_out, session_count fields."""
    await api_client.post("/api/profiles", json=VALID_PROFILE)
    resp = await api_client.get("/api/profiles")
    assert resp.status_code == 200
    profiles = resp.json()
    assert len(profiles) > 0
    p = profiles[0]
    assert "total_in"      in p, "total_in missing from profile list"
    assert "total_out"     in p, "total_out missing from profile list"
    assert "session_count" in p, "session_count missing from profile list"
    assert isinstance(p["total_in"],      int)
    assert isinstance(p["total_out"],     int)
    assert isinstance(p["session_count"], int)


@pytest.mark.asyncio
async def test_list_profiles_stats_zero_when_no_events(api_client):
    """A freshly created profile with no sessions has all stats at 0."""
    resp = await api_client.post("/api/profiles", json={**VALID_PROFILE, "name": "Stats Zero Test"})
    profile_id = resp.json()["id"]
    list_resp = await api_client.get("/api/profiles")
    p = next((x for x in list_resp.json() if x["id"] == profile_id), None)
    assert p is not None
    assert p["total_in"]      == 0
    assert p["total_out"]     == 0
    assert p["session_count"] == 0


@pytest.mark.asyncio
async def test_list_profiles_stats_reflect_events(api_client):
    """total_in and total_out reflect actual events inserted for that profile."""
    from backend.db.database import get_connection, insert_event

    resp = await api_client.post("/api/profiles", json={**VALID_PROFILE, "name": "Stats Events Test"})
    profile_id = resp.json()["id"]

    # Create a session via API
    sess_resp = await api_client.post("/api/sessions/start", json={"profile_id": profile_id})
    assert sess_resp.status_code in (200, 201)
    session_id = sess_resp.json()["session_id"]

    # Insert 2 IN + 1 OUT events directly into the DB
    conn = get_connection()
    try:
        insert_event(conn, session_id, profile_id, "in",  1)
        insert_event(conn, session_id, profile_id, "in",  2)
        insert_event(conn, session_id, profile_id, "out", 1)
    finally:
        conn.close()

    list_resp = await api_client.get("/api/profiles")
    p = next((x for x in list_resp.json() if x["id"] == profile_id), None)
    assert p is not None
    assert p["total_in"]  == 2
    assert p["total_out"] == 1
