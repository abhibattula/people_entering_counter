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


# ── YOLO heatmap bias (T010) ──────────────────────────────────────────────

def test_proposal_roi_overlaps_yolo_person_corridor():
    """ROI polygon must favour the region where people appeared in YOLO detections."""
    import numpy as np
    from unittest.mock import patch
    from tests.conftest import make_mock_yolo, make_solid_frame
    from backend.services.calibration_service import propose_doorway

    # Frames: dark background with a bright rectangle on the LEFT half
    frames = []
    for _ in range(5):
        f = make_solid_frame(640, 480, color=(30, 30, 30))
        f[:, :320] = (180, 180, 180)          # bright left half only
        frames.append(f)

    # YOLO detects people only in the LEFT half
    person_in_left = make_mock_yolo([[20, 100, 200, 400]])  # box entirely in x < 320

    with patch("backend.services.calibration_service.get_model", return_value=person_in_left):
        result = propose_doorway(frames, mode="photo")

    roi = result["roi_polygon"]
    xs = [pt[0] for pt in roi]
    # The centroid of the proposed ROI should be in the left half of the 640-wide frame
    assert (min(xs) + max(xs)) / 2 < 400, (
        f"ROI centroid x={((min(xs)+max(xs))/2):.0f} expected in left half (x<400)"
    )


# ── Polygon corner selection (T011) ──────────────────────────────────────

def test_polygon_has_exactly_four_corners(mock_yolo):
    from backend.services.calibration_service import propose_doorway
    with patch("backend.services.calibration_service.get_model", return_value=mock_yolo):
        result = propose_doorway(make_frames(), mode="photo")
    assert len(result["roi_polygon"]) == 4


def test_polygon_corners_ordered_tl_tr_br_bl(mock_yolo):
    """Points must be ordered: top-left, top-right, bottom-right, bottom-left."""
    from backend.services.calibration_service import propose_doorway
    with patch("backend.services.calibration_service.get_model", return_value=mock_yolo):
        result = propose_doorway(make_frames(), mode="photo")
    tl, tr, br, bl = result["roi_polygon"]
    # top two have smaller y than bottom two
    assert tl[1] <= br[1] and tl[1] <= bl[1]
    assert tr[1] <= br[1] and tr[1] <= bl[1]
    # left two have smaller x than right two
    assert tl[0] <= tr[0]
    assert bl[0] <= br[0]


# ──────────────────────────────────────────────────────────────────────────

def test_retry_raises_after_max(mock_yolo):
    from backend.services.calibration_service import CalibrationSession, TooManyRetriesError
    session = CalibrationSession()
    with patch("backend.services.calibration_service.get_model", return_value=mock_yolo):
        for _ in range(3):
            session.propose(make_frames(), mode="photo")
        with pytest.raises(TooManyRetriesError):
            session.propose(make_frames(), mode="photo")
