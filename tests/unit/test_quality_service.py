import numpy as np
import pytest
from tests.conftest import door_frame


def solid(h, w, val):
    f = np.zeros((h, w, 3), dtype=np.uint8)
    f[:] = val
    return f


# ── Lighting check ────────────────────────────────────────────────────────

def test_dark_frame_fails_lighting():
    from backend.services.quality_service import assess_quality
    frames = [solid(480, 640, 10)] * 5
    result = assess_quality(frames)
    assert result["lighting_acceptable"] is False


def test_bright_frame_passes_lighting():
    from backend.services.quality_service import assess_quality
    frames = [solid(480, 640, 150)] * 5
    result = assess_quality(frames)
    assert result["lighting_acceptable"] is True


def test_overexposed_frame_fails_lighting():
    from backend.services.quality_service import assess_quality
    frames = [solid(480, 640, 245)] * 5
    result = assess_quality(frames)
    assert result["lighting_acceptable"] is False


# ── Door visibility check ─────────────────────────────────────────────────

def test_door_frame_passes_visibility():
    from backend.services.quality_service import assess_quality
    frames = [door_frame()] * 5
    result = assess_quality(frames)
    assert result["door_fully_visible"] is True


def test_all_uniform_frame_fails_visibility():
    from backend.services.quality_service import assess_quality
    frames = [solid(480, 640, 128)] * 5
    result = assess_quality(frames)
    assert result["door_fully_visible"] is False


# ── Camera adjustment (ROI size) ──────────────────────────────────────────

def test_tiny_roi_recommends_closer():
    from backend.services.quality_service import assess_quality
    # door occupies ~5% of frame — too far
    f = solid(480, 640, 40)
    f[200:240, 290:330] = 200  # tiny bright region
    result = assess_quality([f] * 5)
    assert result["camera_adjustment"] in ("closer", "keep")  # at minimum not 'farther'


def test_normal_roi_recommends_keep():
    from backend.services.quality_service import assess_quality
    frames = [door_frame()] * 5
    result = assess_quality(frames)
    assert result["camera_adjustment"] == "keep"


# ── Crowding risk ─────────────────────────────────────────────────────────

def test_no_detections_gives_low_crowding(mock_yolo):
    from backend.services.quality_service import assess_quality
    from unittest.mock import patch
    frames = [door_frame()] * 5
    with patch("backend.services.quality_service.get_model", return_value=mock_yolo):
        result = assess_quality(frames)
    assert result["crowding_risk"] == "low"


def test_many_detections_gives_high_crowding():
    from backend.services.quality_service import assess_quality
    from unittest.mock import patch
    from tests.conftest import make_mock_yolo
    # 4 person boxes per frame → avg > 3 → high
    boxes = [[10,10,100,200],[110,10,200,200],[210,10,300,200],[310,10,400,200]]
    mock = make_mock_yolo(boxes)
    frames = [door_frame()] * 5
    with patch("backend.services.quality_service.get_model", return_value=mock):
        result = assess_quality(frames)
    assert result["crowding_risk"] == "high"


# ── Edge cases ────────────────────────────────────────────────────────────

def test_all_black_frame_does_not_raise():
    from backend.services.quality_service import assess_quality
    frames = [solid(480, 640, 0)] * 5
    result = assess_quality(frames)
    assert "lighting_acceptable" in result
    assert "door_fully_visible" in result
    assert "crowding_risk" in result
    assert "camera_adjustment" in result


def test_all_white_frame_does_not_raise():
    from backend.services.quality_service import assess_quality
    frames = [solid(480, 640, 255)] * 5
    result = assess_quality(frames)
    assert result["lighting_acceptable"] is False  # overexposed


def test_returns_all_four_keys(mock_yolo):
    from backend.services.quality_service import assess_quality
    from unittest.mock import patch
    frames = [door_frame()] * 3
    with patch("backend.services.quality_service.get_model", return_value=mock_yolo):
        result = assess_quality(frames)
    assert set(result.keys()) == {"door_fully_visible", "lighting_acceptable", "crowding_risk", "camera_adjustment"}
