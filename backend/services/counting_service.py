import asyncio
import collections
import threading
import time
from typing import Optional, List, Tuple

import cv2
import numpy as np

from backend.config import MODEL_VARIANT
from backend.services.model_service import get_model

# ── Pure functions (testable without camera) ──────────────────────────────


def detect_crossing(
    prev_centroid: Tuple[int, int],
    curr_centroid: Tuple[int, int],
    line: dict,
    inside_direction: str,
) -> Optional[str]:
    """
    Return "in", "out", or None based on whether the centroid crossed the line.
    Line is defined by {x1,y1,x2,y2}. inside_direction is "up"|"down"|"left"|"right".
    """
    if inside_direction in ("up", "down"):
        mid_y = (line["y1"] + line["y2"]) / 2
        prev_above = prev_centroid[1] < mid_y
        curr_above = curr_centroid[1] < mid_y
        if prev_above == curr_above:
            return None
        # crossed — determine direction
        moved_up = curr_above  # True = moved to lower y
        if inside_direction == "up":
            return "in" if moved_up else "out"
        else:  # "down"
            return "out" if moved_up else "in"
    else:  # "left" or "right"
        mid_x = (line["x1"] + line["x2"]) / 2
        prev_left = prev_centroid[0] < mid_x
        curr_left = curr_centroid[0] < mid_x
        if prev_left == curr_left:
            return None
        moved_left = curr_left
        if inside_direction == "left":
            return "in" if moved_left else "out"
        else:  # "right"
            return "out" if moved_left else "in"


def is_inside_roi(centroid: Tuple[int, int], polygon: List[List[int]]) -> bool:
    """Return True if centroid is within the ROI polygon."""
    pts = np.array(polygon, dtype=np.int32)
    result = cv2.pointPolygonTest(pts, (float(centroid[0]), float(centroid[1])), False)
    return result >= 0


# ── Occupancy tracker ─────────────────────────────────────────────────────


class OccupancyTracker:
    def __init__(self):
        self.in_count = 0
        self.out_count = 0

    @property
    def occupancy(self) -> int:
        return max(0, self.in_count - self.out_count)

    def record(self, direction: str) -> None:
        if direction == "in":
            self.in_count += 1
        elif direction == "out":
            self.out_count += 1


# ── Live counting service ─────────────────────────────────────────────────


class CountingService:
    """
    Runs YOLOv8 + ByteTrack in a background thread.
    Produces MJPEG frames and pushes CrossingEvents to an asyncio queue.
    """

    def __init__(self):
        self._cap: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._paused = False
        self._profile: Optional[dict] = None
        self._latest_frame: Optional[bytes] = None
        self._frame_lock = threading.Lock()
        self._event_queues: list[asyncio.Queue] = []
        self._queues_lock = threading.Lock()
        self._occupancy = OccupancyTracker()
        self._prev_centroids: dict[int, Tuple[int, int]] = {}
        self._frame_times: collections.deque = collections.deque(maxlen=30)

    # ── Public interface ──────────────────────────────────────────────────

    def start(self, profile: dict, camera_index: int = 0) -> None:
        if self._running:
            return
        self._profile = profile
        self._occupancy = OccupancyTracker()
        self._prev_centroids = {}
        self._cap = cv2.VideoCapture(camera_index)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open camera {camera_index}")
        self._running = True
        self._paused = False
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        if self._cap:
            self._cap.release()
            self._cap = None
        self._latest_frame = None

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def is_running(self) -> bool:
        return self._running

    def get_fps(self) -> float:
        d = self._frame_times
        if len(d) >= 2:
            return len(d) / (d[-1] - d[0])
        return 0.0

    def get_latest_frame(self) -> Optional[bytes]:
        with self._frame_lock:
            return self._latest_frame

    def subscribe(self, queue: asyncio.Queue) -> None:
        with self._queues_lock:
            self._event_queues.append(queue)

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        with self._queues_lock:
            self._event_queues = [q for q in self._event_queues if q is not queue]

    # ── Background loop ───────────────────────────────────────────────────

    def _loop(self) -> None:
        model = get_model()
        profile = self._profile
        roi = profile["roi_polygon"]
        line = profile["counting_line"]
        direction = profile["inside_direction"]

        while self._running:
            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            results = model.track(frame, persist=True, verbose=False, tracker="bytetrack.yaml")

            annotated = frame.copy()
            self._draw_overlays(annotated, roi, line, direction)

            if not self._paused and results:
                for r in results:
                    if r.boxes is None or r.boxes.id is None:
                        continue
                    boxes = r.boxes.xyxy.cpu().numpy() if hasattr(r.boxes.xyxy, "cpu") else r.boxes.xyxy
                    ids = r.boxes.id.cpu().numpy().astype(int) if hasattr(r.boxes.id, "cpu") else r.boxes.id.astype(int)
                    cls = r.boxes.cls.cpu().numpy() if hasattr(r.boxes.cls, "cpu") else r.boxes.cls

                    for box, track_id, c in zip(boxes, ids, cls):
                        if int(c) != 0:  # only persons
                            continue
                        cx = int((box[0] + box[2]) / 2)
                        cy = int((box[1] + box[3]) / 2)
                        centroid = (cx, cy)

                        if not is_inside_roi(centroid, roi):
                            continue

                        cv2.rectangle(annotated, (int(box[0]), int(box[1])), (int(box[2]), int(box[3])), (0, 255, 0), 2)
                        cv2.putText(annotated, f"ID:{track_id}", (int(box[0]), int(box[1]) - 5),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

                        if track_id in self._prev_centroids:
                            crossing = detect_crossing(
                                self._prev_centroids[track_id], centroid, line, direction
                            )
                            if crossing:
                                self._occupancy.record(crossing)
                                self._emit_event(crossing, self._occupancy.occupancy)

                        self._prev_centroids[track_id] = centroid

            # FPS tracking
            self._frame_times.append(time.time())

            # FPS + model overlay (top-left, black shadow then white text)
            fps_text = f"{self.get_fps():.1f} fps"
            model_text = MODEL_VARIANT
            font = cv2.FONT_HERSHEY_SIMPLEX
            scale, thickness, shadow = 0.6, 2, 1
            for i, text in enumerate((fps_text, model_text)):
                y = 25 + i * 25
                # black shadow (1px offset)
                cv2.putText(annotated, text, (11, y + 1), font, scale, (0, 0, 0), thickness + shadow)
                # white text
                cv2.putText(annotated, text, (10, y), font, scale, (255, 255, 255), thickness)

            _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
            with self._frame_lock:
                self._latest_frame = buf.tobytes()

    def _draw_overlays(self, frame, roi, line, direction):
        # ROI polygon (purple dashed)
        pts = np.array(roi, dtype=np.int32).reshape(-1, 1, 2)
        cv2.polylines(frame, [pts], True, (128, 0, 128), 1, cv2.LINE_AA)
        # Counting line (yellow)
        cv2.line(frame, (line["x1"], line["y1"]), (line["x2"], line["y2"]), (0, 255, 255), 2)
        # Direction arrow
        mx = (line["x1"] + line["x2"]) // 2
        my = line["y1"]
        dmap = {"up": (0, -25), "down": (0, 25), "left": (-25, 0), "right": (25, 0)}
        dx, dy = dmap.get(direction, (0, -25))
        cv2.arrowedLine(frame, (mx, my), (mx + dx, my + dy), (0, 200, 0), 2, tipLength=0.4)

    def _emit_event(self, direction: str, occupancy: int) -> None:
        from datetime import datetime, timezone
        import json
        payload = {
            "direction": direction,
            "occupancy": occupancy,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._queues_lock:
            for q in self._event_queues:
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:
                    pass


# ── Module-level singleton registry (one service per profile_id) ──────────

_services: dict[str, CountingService] = {}
_services_lock = threading.Lock()


def get_or_create_service(profile_id: str) -> CountingService:
    with _services_lock:
        if profile_id not in _services:
            _services[profile_id] = CountingService()
        return _services[profile_id]


def stop_service(profile_id: str) -> None:
    with _services_lock:
        svc = _services.pop(profile_id, None)
    if svc:
        svc.stop()
