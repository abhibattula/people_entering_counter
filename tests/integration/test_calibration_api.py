import io
import pytest
import pytest_asyncio
import numpy as np
import cv2
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport


def make_jpeg_bytes(w=640, h=480, val=128):
    frame = np.full((h, w, 3), val, dtype=np.uint8)
    # add a bright rectangle to simulate a door
    frame[80:400, 160:480] = 200
    _, buf = cv2.imencode(".jpg", frame)
    return buf.tobytes()


def build_multipart_files(n=5, mode="photo"):
    files = [("frames", (f"frame{i}.jpg", make_jpeg_bytes(), "image/jpeg")) for i in range(n)]
    data = {"mode": mode}
    return files, data


@pytest.fixture()
def mock_services():
    fake_proposal = {
        "roi_polygon": [[100,50],[500,50],[500,400],[100,400]],
        "counting_line": {"x1": 100, "y1": 225, "x2": 500, "y2": 225},
        "inside_direction": "up",
        "confidence": 0.85,
        "best_frame_b64": "/9j/fake",
        "manual_fallback_available": False,
    }
    fake_quality = {
        "door_fully_visible": True,
        "lighting_acceptable": True,
        "crowding_risk": "low",
        "camera_adjustment": "keep",
    }
    with patch("backend.routers.calibration._get_or_create_session") as mock_sess, \
         patch("backend.services.quality_service.assess_quality", return_value=fake_quality), \
         patch("backend.services.calibration_service.CalibrationSession.propose", return_value={**fake_proposal}):
        session_mock = MagicMock()
        session_mock.propose.return_value = {**fake_proposal}
        mock_sess.return_value = session_mock
        yield fake_quality, fake_proposal


@pytest_asyncio.fixture()
async def api_client():
    from backend.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_calibrate_frames_returns_200(api_client, mock_services):
    files, data = build_multipart_files(5, "photo")
    resp = await api_client.post("/api/calibrate/frames", files=files, data=data)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_calibrate_frames_response_has_quality_check(api_client, mock_services):
    files, data = build_multipart_files(5, "photo")
    resp = await api_client.post("/api/calibrate/frames", files=files, data=data)
    body = resp.json()
    assert "quality_check" in body
    qc = body["quality_check"]
    assert "door_fully_visible" in qc
    assert "lighting_acceptable" in qc
    assert "crowding_risk" in qc
    assert "camera_adjustment" in qc


@pytest.mark.asyncio
async def test_calibrate_frames_response_has_proposal(api_client, mock_services):
    files, data = build_multipart_files(5, "photo")
    resp = await api_client.post("/api/calibrate/frames", files=files, data=data)
    body = resp.json()
    assert "proposal" in body
    p = body["proposal"]
    assert len(p["roi_polygon"]) == 4
    assert all(k in p["counting_line"] for k in ("x1","y1","x2","y2"))
    assert p["inside_direction"] in ("up","down","left","right")


@pytest.mark.asyncio
async def test_calibrate_frames_rejects_zero_frames(api_client, mock_services):
    resp = await api_client.post("/api/calibrate/frames", files=[], data={"mode": "photo"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_calibrate_frames_rejects_invalid_mode(api_client, mock_services):
    files, _ = build_multipart_files(3, "photo")
    resp = await api_client.post("/api/calibrate/frames", files=files, data={"mode": "invalid"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_calibrate_frames_video_mode_same_schema(api_client, mock_services):
    files, data = build_multipart_files(15, "video")
    resp = await api_client.post("/api/calibrate/frames", files=files, data=data)
    assert resp.status_code == 200
    body = resp.json()
    assert "quality_check" in body
    assert "proposal" in body


@pytest.mark.asyncio
async def test_calibrate_retry_returns_200(api_client, mock_services):
    files, data = build_multipart_files(5, "photo")
    resp = await api_client.post("/api/calibrate/retry", files=files, data=data)
    assert resp.status_code == 200
