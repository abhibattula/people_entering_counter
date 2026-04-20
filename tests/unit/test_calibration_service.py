import numpy as np
import pytest
from unittest.mock import patch
from tests.conftest import make_mock_yolo, door_frame


def make_frames(n=5):
    return [door_frame()] * n


# ── Basic proposal shape ──────────────────────────────────────────────────

def test_propose_returns_roi_polygon(mock_yolo):
    from backend.services.calibration_service import propose_doorway
    with patch("backend.services.calibration_service.get_model", return_value=mock_yolo):
        result = propose_doorway(make_frames(), mode="photo")
    assert "roi_polygon" in result
    assert len(result["roi_polygon"]) == 4


def test_propose_returns_counting_line(mock_yolo):
    from backend.services.calibration_service import propose_doorway
    with patch("backend.services.calibration_service.get_model", return_value=mock_yolo):
        result = propose_doorway(make_frames(), mode="photo")
    line = result["counting_line"]
    assert all(k in line for k in ("x1", "y1", "x2", "y2"))


def test_propose_returns_inside_direction(mock_yolo):
    from backend.services.calibration_service import propose_doorway
    with patch("backend.services.calibration_service.get_model", return_value=mock_yolo):
        result = propose_doorway(make_frames(), mode="photo")
    assert result["inside_direction"] in ("up", "down", "left", "right")


def test_propose_returns_confidence_between_0_and_1(mock_yolo):
    from backend.services.calibration_service import propose_doorway
    with patch("backend.services.calibration_service.get_model", return_value=mock_yolo):
        result = propose_doorway(make_frames(), mode="photo")
    assert 0.0 <= result["confidence"] <= 1.0


def test_propose_returns_best_frame_b64(mock_yolo):
    from backend.services.calibration_service import propose_doorway
    import base64
    with patch("backend.services.calibration_service.get_model", return_value=mock_yolo):
        result = propose_doorway(make_frames(), mode="photo")
    b64 = result["best_frame_b64"]
    # must be valid base64-encoded JPEG (starts with /9j in base64)
    decoded = base64.b64decode(b64)
    assert decoded[:2] == b"\xff\xd8"  # JPEG magic bytes


def test_counting_line_within_roi_y_bounds(mock_yolo):
    from backend.services.calibration_service import propose_doorway
    with patch("backend.services.calibration_service.get_model", return_value=mock_yolo):
        result = propose_doorway(make_frames(), mode="photo")
    ys = [pt[1] for pt in result["roi_polygon"]]
    line = result["counting_line"]
    assert min(ys) <= line["y1"] <= max(ys)
    assert min(ys) <= line["y2"] <= max(ys)


# ── Retry tracking ────────────────────────────────────────────────────────

def test_retry_counter_increments(mock_yolo):
    from backend.services.calibration_service import CalibrationSession
    session = CalibrationSession()
    with patch("backend.services.calibration_service.get_model", return_value=mock_yolo):
        session.propose(make_frames(), mode="photo")
        assert session.retry_count == 0
        session.propose(make_frames(), mode="photo")
        assert session.retry_count == 1
        session.propose(make_frames(), mode="photo")
        assert session.retry_count == 2


def test_manual_fallback_available_after_two_retries(mock_yolo):
    from backend.services.calibration_service import CalibrationSession
    session = CalibrationSession()
    with patch("backend.services.calibration_service.get_model", return_value=mock_yolo):
        for _ in range(3):
            result = session.propose(make_frames(), mode="photo")
    assert result["manual_fallback_available"] is True


def test_manual_fallback_not_available_on_first_try(mock_yolo):
    from backend.services.calibration_service import CalibrationSession
    session = CalibrationSession()
    with patch("backend.services.calibration_service.get_model", return_value=mock_yolo):
        result = session.propose(make_frames(), mode="photo")
    assert result["manual_fallback_available"] is False


def test_retry_raises_after_max(mock_yolo):
    from backend.services.calibration_service import CalibrationSession, TooManyRetriesError
    session = CalibrationSession()
    with patch("backend.services.calibration_service.get_model", return_value=mock_yolo):
        for _ in range(3):
            session.propose(make_frames(), mode="photo")
        with pytest.raises(TooManyRetriesError):
            session.propose(make_frames(), mode="photo")
