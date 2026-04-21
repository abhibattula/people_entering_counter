"""Integration tests for the grayscale query parameter on GET /stream. (T025)"""
import json
import uuid
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock


def _make_profile(profile_id: str) -> dict:
    return {
        "id": profile_id,
        "name": "Test",
        "camera_index": 0,
        "capture_mode": "photo",
        "frame_width": 640,
        "frame_height": 480,
        "roi_polygon": [[0, 0], [640, 0], [640, 480], [0, 480]],
        "counting_line": {"x1": 0, "y1": 240, "x2": 640, "y2": 240},
        "inside_direction": "down",
        "door_randomly_opens": False,
        "quality_check": {
            "door_fully_visible": True,
            "lighting_acceptable": True,
            "crowding_risk": "low",
            "camera_adjustment": "keep",
        },
        "created_at": "2026-04-21T00:00:00Z",
    }


def _make_service_mock():
    svc = MagicMock()
    # True ×3 (route check, generator check, first while iteration), then False to exit generator
    svc.is_running.side_effect = [True, True, True, False]
    svc.get_latest_frame.return_value = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # minimal JPEG-like bytes
    svc.set_grayscale = MagicMock()
    return svc


@pytest.fixture()
def profile_id():
    return f"test-{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture()
async def stream_client(profile_id):
    from httpx import AsyncClient, ASGITransport
    from backend.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_stream_calls_set_grayscale_true(profile_id, stream_client):
    """GET /stream?grayscale=true must call svc.set_grayscale(True)."""
    profile = _make_profile(profile_id)
    mock_svc = _make_service_mock()

    with patch("backend.routers.stream._load_profile", return_value=profile), \
         patch("backend.routers.stream.get_or_create_service", return_value=mock_svc):

        await stream_client.get(
            f"/stream?profile_id={profile_id}&grayscale=true",
        )

    mock_svc.set_grayscale.assert_called_once_with(True)


@pytest.mark.asyncio
async def test_stream_calls_set_grayscale_false_by_default(profile_id, stream_client):
    """GET /stream without grayscale param must call svc.set_grayscale(False)."""
    profile = _make_profile(profile_id)
    mock_svc = _make_service_mock()

    with patch("backend.routers.stream._load_profile", return_value=profile), \
         patch("backend.routers.stream.get_or_create_service", return_value=mock_svc):

        await stream_client.get(
            f"/stream?profile_id={profile_id}",
        )

    mock_svc.set_grayscale.assert_called_once_with(False)
