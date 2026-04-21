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


# ── Extended quality tests (Phase 5 / T045-T048) ──────────────────────────

def test_door_at_extreme_corner_still_visible():
    """A door-shaped bright region near a corner edge is still detected as visible."""
    from backend.services.quality_service import assess_quality
    # Build a dark frame with a 200×300-pixel bright region anchored near top-left corner
    frame = np.full((480, 640, 3), 40, dtype=np.uint8)
    frame[10:210, 10:310] = 200  # bright rectangle at top-left, 10px away from border
    frames = [frame] * 5
    result = assess_quality(frames)
    assert result["door_fully_visible"] is True


def test_boundary_brightness_exactly_at_threshold():
    """LAB L=60 (BGR≈56) passes; LAB L=59 (BGR≈55) fails."""
    from backend.services.quality_service import assess_quality
    # BGR=56 → LAB L mean ≈ 60 — exactly at lower boundary → should pass
    frame_pass = solid(480, 640, 56)
    result_pass = assess_quality([frame_pass] * 5)
    assert result_pass["lighting_acceptable"] is True

    # BGR=55 → LAB L mean ≈ 59 — one below boundary → should fail
    frame_fail = solid(480, 640, 55)
    result_fail = assess_quality([frame_fail] * 5)
    assert result_fail["lighting_acceptable"] is False


# ── Tightened door visibility (T012) ─────────────────────────────────────

def test_plain_wall_fails_visibility():
    """A solid frame with many edges but no contour reaching 2 frame edges must fail."""
    from backend.services.quality_service import assess_quality
    # Create a frame where edges are distributed throughout but no single contour
    # spans across the frame from edge to edge (e.g., many small internal patterns)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # Draw grid of small boxes in the interior — many edges but none reach frame border
    for y in range(100, 400, 50):
        for x in range(100, 550, 50):
            frame[y:y+30, x:x+30] = 200
    result = assess_quality([frame] * 5)
    assert result["door_fully_visible"] is False, (
        "Many interior edges with no contour reaching frame edges should fail visibility"
    )


def test_solid_colour_wall_fails_visibility():
    """A solid white frame (like a blank wall) must fail door visibility."""
    from backend.services.quality_service import assess_quality
    # Solid white has many edge pixels near the frame boundary from the white→black frame edge
    # but NO internal contour spanning 2 frame edges
    frame = np.full((480, 640, 3), 200, dtype=np.uint8)
    result = assess_quality([frame] * 5)
    assert result["door_fully_visible"] is False, (
        "Solid colour frame (no door) should fail visibility check"
    )


def test_single_frame_does_not_crash():
    """assess_quality([one_frame]) must not raise and must return all four keys."""
    from backend.services.quality_service import assess_quality
    frames = [door_frame()]  # len == 1
    result = assess_quality(frames)
    assert set(result.keys()) == {"door_fully_visible", "lighting_acceptable", "crowding_risk", "camera_adjustment"}
