import asyncio
import sqlite3
import numpy as np
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, patch


# ── Synthetic frame helpers ────────────────────────────────────────────────


def make_solid_frame(width=640, height=480, color=(128, 128, 128)):
    """Return a solid-colour BGR numpy frame."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = color
    return frame


def door_frame(height=480, width=640):
    """Dark frame with bright centre rectangle simulating a lit doorway."""
    frame = make_solid_frame(width, height, color=(40, 40, 40))
    frame[80:400, 160:480] = (200, 200, 200)
    return frame


def make_gradient_frame(width=640, height=480):
    """Return a left-to-right brightness gradient BGR frame."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    for x in range(width):
        val = int(x / width * 255)
        frame[:, x] = (val, val, val)
    return frame


def make_door_frame(width=640, height=480):
    """Return a frame with a bright rectangle simulating a lit doorway."""
    frame = make_solid_frame(width, height, color=(60, 60, 60))
    # bright doorway region in the centre
    cv_x1, cv_y1, cv_x2, cv_y2 = width // 4, height // 6, 3 * width // 4, 5 * height // 6
    frame[cv_y1:cv_y2, cv_x1:cv_x2] = (200, 200, 200)
    return frame


def frames_to_jpeg_bytes(frames):
    """Encode list of numpy frames to JPEG bytes list."""
    import cv2
    result = []
    for f in frames:
        _, buf = cv2.imencode(".jpg", f)
        result.append(buf.tobytes())
    return result


# ── In-memory SQLite DB ───────────────────────────────────────────────────


@pytest.fixture()
def mem_db():
    """Provide an in-memory SQLite connection with the app schema applied."""
    from backend.db.database import SCHEMA_SQL
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    yield conn
    conn.close()


# ── Mock YOLO model ───────────────────────────────────────────────────────


class MockYOLOResult:
    """Minimal stand-in for an ultralytics Results object."""

    def __init__(self, boxes=None):
        self.boxes = boxes or MockBoxes([])

    def __iter__(self):
        yield self


class MockBoxes:
    def __init__(self, xyxy_list, cls_list=None):
        # each xyxy is [x1, y1, x2, y2]
        self.xyxy = np.array(xyxy_list, dtype=np.float32).reshape(-1, 4) if xyxy_list else np.zeros((0, 4))
        self.cls = np.array(cls_list or [0] * len(xyxy_list), dtype=np.float32)
        self.id = None  # no tracking IDs by default


def make_mock_yolo(detections=None):
    """
    Return a mock YOLO model callable.
    detections: list of [x1,y1,x2,y2] boxes (person class=0).
    """
    result = MockYOLOResult(MockBoxes(detections or []))
    model = MagicMock()
    model.return_value = [result]
    model.track = MagicMock(return_value=[result])
    return model


@pytest.fixture()
def mock_yolo():
    return make_mock_yolo()


@pytest.fixture()
def mock_yolo_with_person():
    """A mock model that returns one centred person detection."""
    return make_mock_yolo([[200, 100, 440, 460]])


# ── FastAPI test client ───────────────────────────────────────────────────


@pytest_asyncio.fixture()
async def client():
    """Async HTTP client wired to the FastAPI app with a fresh in-memory DB."""
    with patch("backend.services.model_service._model", make_mock_yolo()):
        from backend.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
