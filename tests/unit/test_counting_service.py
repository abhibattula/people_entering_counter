import pytest


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
