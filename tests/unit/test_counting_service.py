import collections
import numpy as np
import pytest
from unittest.mock import MagicMock, patch, call
import cv2


# ── FPS guard (T002) ──────────────────────────────────────────────────────

def test_get_fps_returns_zero_when_all_timestamps_identical():
    from backend.services.counting_service import CountingService
    svc = CountingService()
    svc._frame_times = collections.deque([1000.0, 1000.0, 1000.0], maxlen=30)
    assert svc.get_fps() == 0.0


def test_get_fps_no_division_by_zero():
    from backend.services.counting_service import CountingService
    svc = CountingService()
    svc._frame_times = collections.deque([5.0, 5.0], maxlen=30)
    result = svc.get_fps()  # must not raise ZeroDivisionError
    assert result == 0.0


def test_get_fps_correct_interval_formula():
    from backend.services.counting_service import CountingService
    svc = CountingService()
    # 3 frames spanning 2 seconds → 2 intervals / 2 s = 1.0 fps
    svc._frame_times = collections.deque([0.0, 1.0, 2.0], maxlen=30)
    assert svc.get_fps() == pytest.approx(1.0)


# ── Thread exception logging (T004) ──────────────────────────────────────

def test_loop_logs_exception_and_sets_running_false(caplog):
    import logging
    from backend.services.counting_service import CountingService

    svc = CountingService()
    svc._running = True
    svc._paused = False
    svc._profile = {
        "roi_polygon": [[0, 0], [640, 0], [640, 480], [0, 480]],
        "counting_line": {"x1": 0, "y1": 240, "x2": 640, "y2": 240},
        "inside_direction": "down",
    }
    mock_cap = MagicMock()
    mock_cap.read.side_effect = RuntimeError("simulated camera error")
    svc._cap = mock_cap

    with caplog.at_level(logging.ERROR):
        with patch("backend.services.counting_service.get_model"):
            svc._loop()

    assert not svc._running
    assert any("simulated camera error" in m or "error" in m.lower()
               for m in (r.message for r in caplog.records))


# ── Camera resolution (T006) ──────────────────────────────────────────────

def test_start_applies_profile_resolution_to_camera():
    from backend.services.counting_service import CountingService

    profile = {
        "frame_width": 1280,
        "frame_height": 720,
        "roi_polygon": [[0, 0], [1280, 0], [1280, 720], [0, 720]],
        "counting_line": {"x1": 0, "y1": 360, "x2": 1280, "y2": 360},
        "inside_direction": "down",
    }
    svc = CountingService()
    with patch("backend.services.counting_service.cv2.VideoCapture") as MockVC:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 1280.0  # pretend camera honours the request
        MockVC.return_value = mock_cap
        svc.start(profile, camera_index=0)
        svc.stop()

    mock_cap.set.assert_any_call(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    mock_cap.set.assert_any_call(cv2.CAP_PROP_FRAME_HEIGHT, 720)


# ── Detection without tracking ID (T007) ─────────────────────────────────

def test_detection_drawn_when_no_tracking_id():
    """cv2.rectangle must be called for persons inside ROI even when r.boxes.id is None."""
    from backend.services.counting_service import CountingService

    svc = CountingService()
    roi = [[0, 0], [640, 0], [640, 480], [0, 480]]
    line = {"x1": 0, "y1": 240, "x2": 640, "y2": 240}

    mock_result = MagicMock()
    mock_result.boxes.id = None
    mock_result.boxes.xyxy = np.array([[100.0, 100.0, 300.0, 400.0]], dtype=np.float32)
    mock_result.boxes.cls = np.array([0.0], dtype=np.float32)

    annotated = np.zeros((480, 640, 3), dtype=np.uint8)

    with patch("backend.services.counting_service.cv2.rectangle") as mock_rect:
        svc._render_detections([mock_result], roi, line, "down", annotated)
        assert mock_rect.called, "cv2.rectangle must be called even without track IDs"


def test_no_crossing_recorded_when_no_tracking_id():
    """Line-crossing events must NOT be emitted for detections without track IDs."""
    from backend.services.counting_service import CountingService

    svc = CountingService()
    roi = [[0, 0], [640, 0], [640, 480], [0, 480]]
    line = {"x1": 0, "y1": 240, "x2": 640, "y2": 240}

    mock_result = MagicMock()
    mock_result.boxes.id = None
    mock_result.boxes.xyxy = np.array([[100.0, 50.0, 300.0, 250.0]], dtype=np.float32)
    mock_result.boxes.cls = np.array([0.0], dtype=np.float32)

    crossings = svc._check_crossings([mock_result], roi, line, "down")
    assert crossings == [], "No crossings should be emitted without track IDs"


# ── Line-crossing logic ───────────────────────────────────────────────────

def test_centroid_above_to_below_is_in():
    from backend.services.counting_service import detect_crossing
    line = {"x1": 0, "y1": 240, "x2": 640, "y2": 240}
    # inside_direction="down" means moving to higher y is "in"
    result = detect_crossing(
        prev_centroid=(320, 200),  # above line
        curr_centroid=(320, 280),  # below line
        line=line,
        inside_direction="down",
    )
    assert result == "in"


def test_centroid_below_to_above_is_out():
    from backend.services.counting_service import detect_crossing
    line = {"x1": 0, "y1": 240, "x2": 640, "y2": 240}
    result = detect_crossing(
        prev_centroid=(320, 280),
        curr_centroid=(320, 200),
        line=line,
        inside_direction="down",
    )
    assert result == "out"


def test_no_crossing_same_side():
    from backend.services.counting_service import detect_crossing
    line = {"x1": 0, "y1": 240, "x2": 640, "y2": 240}
    result = detect_crossing(
        prev_centroid=(320, 200),
        curr_centroid=(320, 210),
        line=line,
        inside_direction="down",
    )
    assert result is None


def test_crossing_up_direction():
    from backend.services.counting_service import detect_crossing
    line = {"x1": 0, "y1": 240, "x2": 640, "y2": 240}
    # inside_direction="up" means moving to lower y is "in"
    result = detect_crossing(
        prev_centroid=(320, 280),  # below line (high y)
        curr_centroid=(320, 200),  # above line (low y) — moving "up"
        line=line,
        inside_direction="up",
    )
    assert result == "in"


def test_crossing_left_direction():
    from backend.services.counting_service import detect_crossing
    line = {"x1": 320, "y1": 0, "x2": 320, "y2": 480}
    # inside_direction="left" means moving to lower x is "in"
    result = detect_crossing(
        prev_centroid=(400, 240),  # right of line
        curr_centroid=(200, 240),  # left of line
        line=line,
        inside_direction="left",
    )
    assert result == "in"


def test_crossing_right_direction():
    from backend.services.counting_service import detect_crossing
    line = {"x1": 320, "y1": 0, "x2": 320, "y2": 480}
    result = detect_crossing(
        prev_centroid=(200, 240),
        curr_centroid=(400, 240),
        line=line,
        inside_direction="right",
    )
    assert result == "in"


# ── Occupancy management ──────────────────────────────────────────────────

def test_occupancy_increments_on_in():
    from backend.services.counting_service import OccupancyTracker
    tracker = OccupancyTracker()
    tracker.record("in")
    assert tracker.occupancy == 1


def test_occupancy_decrements_on_out():
    from backend.services.counting_service import OccupancyTracker
    tracker = OccupancyTracker()
    tracker.record("in")
    tracker.record("out")
    assert tracker.occupancy == 0


def test_occupancy_floored_at_zero():
    from backend.services.counting_service import OccupancyTracker
    tracker = OccupancyTracker()
    tracker.record("out")  # more outs than ins
    assert tracker.occupancy == 0


def test_occupancy_counts():
    from backend.services.counting_service import OccupancyTracker
    tracker = OccupancyTracker()
    for _ in range(3):
        tracker.record("in")
    tracker.record("out")
    assert tracker.in_count == 3
    assert tracker.out_count == 1
    assert tracker.occupancy == 2


# ── ROI containment ───────────────────────────────────────────────────────

def test_centroid_inside_roi_is_tracked():
    from backend.services.counting_service import is_inside_roi
    polygon = [[100, 100], [500, 100], [500, 400], [100, 400]]
    assert is_inside_roi((300, 250), polygon) is True


def test_centroid_outside_roi_is_not_tracked():
    from backend.services.counting_service import is_inside_roi
    polygon = [[100, 100], [500, 100], [500, 400], [100, 400]]
    assert is_inside_roi((50, 50), polygon) is False


# ── Stop order (Task 1 fix) ───────────────────────────────────────────────

def test_stop_releases_camera_before_joining_thread():
    """Camera must be released BEFORE the thread is joined so the thread can detect
    the release via cap.read() → ret=False and exit without waiting for YOLO."""
    import threading
    from backend.services.counting_service import CountingService

    svc = CountingService()
    mock_cap = MagicMock()
    mock_thread = MagicMock(spec=threading.Thread)

    svc._cap = mock_cap
    svc._thread = mock_thread
    svc._running = True

    call_order = []
    mock_cap.release.side_effect = lambda: call_order.append("cap_release")
    mock_thread.join.side_effect = lambda timeout=None: call_order.append("thread_join")

    svc.stop()

    assert call_order == ["cap_release", "thread_join"], (
        f"Expected camera release BEFORE thread join, got: {call_order}"
    )
    assert svc._cap is None
    assert not svc._running
    assert svc._latest_frame is None
