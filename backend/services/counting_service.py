import asyncio
import collections
import logging
import threading
import time
from typing import Optional, List, Tuple

import cv2
import numpy as np

from backend.config import MODEL_VARIANT
from backend.services.model_service import get_model

logger = logging.getLogger(__name__)

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
        moved_up = curr_above
        if inside_direction == "up":
            return "in" if moved_up else "out"
        else:
            return "out" if moved_up else "in"
    else:
        mid_x = (line["x1"] + line["x2"]) / 2
        prev_left = prev_centroid[0] < mid_x
        curr_left = curr_centroid[0] < mid_x
        if prev_left == curr_left:
            return None
        moved_left = curr_left
        if inside_direction == "left":
            return "in" if moved_left else "out"
        else:
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
        self._grayscale = False
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
        # Apply profile resolution so ROI coordinates match actual frame size
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, profile["frame_width"])
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, profile["frame_height"])
        actual_w = self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_h = self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        if actual_w != profile["frame_width"] or actual_h != profile["frame_height"]:
            logger.warning(
                "Camera returned %dx%d but profile requested %dx%d",
                int(actual_w), int(actual_h),
                profile["frame_width"], profile["frame_height"],
            )
        self._running = True
        self._paused = False
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._cap:           # release FIRST — unblocks the loop via ret=False
            self._cap.release()
            self._cap = None
        if self._thread:        # join AFTER — thread exits quickly once cap is gone
            self._thread.join(timeout=5)
        self._latest_frame = None

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def is_running(self) -> bool:
        return self._running

    def set_grayscale(self, enabled: bool) -> None:
        self._grayscale = enabled

    def set_direction(self, direction: str) -> None:
        if self._profile:
            self._profile["inside_direction"] = direction

    def get_fps(self) -> float:
        d = self._frame_times
        if len(d) >= 2 and d[-1] != d[0]:
            return (len(d) - 1) / (d[-1] - d[0])
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
        try:
            model = get_model()
            profile = self._profile
            roi = profile["roi_polygon"]
            line = profile["counting_line"]

            while self._running:
                direction = profile["inside_direction"]  # read each frame so flip takes effect live

                ret, frame = self._cap.read()
                if not ret:
                    time.sleep(0.05)
                    continue

                results = model.track(frame, persist=True, verbose=False, tracker="bytetrack.yaml")

                annotated = frame.copy()
                self._draw_overlays(annotated, roi, line, direction)

                if not self._paused and results:
                    self._render_detections(results, roi, line, direction, annotated)
                    for crossing in self._check_crossings(results, roi, line, direction):
                        self._occupancy.record(crossing)
                        self._emit_event(crossing, self._occupancy.occupancy)

                # FPS tracking
                self._frame_times.append(time.time())

                fps_text = f"{self.get_fps():.1f} fps"
                model_text = MODEL_VARIANT
                font = cv2.FONT_HERSHEY_SIMPLEX
                scale, thickness, shadow = 0.6, 2, 1
                for i, text in enumerate((fps_text, model_text)):
                    y = 25 + i * 25
                    cv2.putText(annotated, text, (11, y + 1), font, scale, (0, 0, 0), thickness + shadow)
                    cv2.putText(annotated, text, (10, y), font, scale, (255, 255, 255), thickness)

                if self._grayscale:
                    annotated = cv2.cvtColor(cv2.cvtColor(annotated, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)

                _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
                with self._frame_lock:
                    self._latest_frame = buf.tobytes()

        except Exception:
            logger.exception("Counting loop error")
            self._running = False

    def _render_detections(self, results, roi, line, direction, annotated) -> None:
        """Draw bounding boxes for all class-0 detections inside ROI regardless of track ID."""
        for r in results:
            if r.boxes is None:
                continue
            boxes = r.boxes.xyxy.cpu().numpy() if hasattr(r.boxes.xyxy, "cpu") else r.boxes.xyxy
            cls = r.boxes.cls.cpu().numpy() if hasattr(r.boxes.cls, "cpu") else r.boxes.cls
            has_ids = r.boxes.id is not None

            for i, (box, c) in enumerate(zip(boxes, cls)):
                if int(c) != 0:
                    continue
                cx = int((box[0] + box[2]) / 2)
                cy = int((box[1] + box[3]) / 2)
                if not is_inside_roi((cx, cy), roi):
                    continue

                if has_ids:
                    color = (0, 255, 0)  # bright green — tracked
                    ids = r.boxes.id.cpu().numpy().astype(int) if hasattr(r.boxes.id, "cpu") else r.boxes.id.astype(int)
                    track_id = ids[i]
                    label = f"ID:{track_id}"
                else:
                    color = (0, 180, 0)  # dim green — detected but not yet tracked
                    label = "person"

                cv2.rectangle(annotated, (int(box[0]), int(box[1])), (int(box[2]), int(box[3])), color, 2)
                cv2.putText(annotated, label, (int(box[0]), int(box[1]) - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    def _check_crossings(self, results, roi, line, direction) -> list:
        """Return list of crossing directions ("in"/"out") for tracked persons crossing the line."""
        crossings = []
        for r in results:
            if r.boxes is None or r.boxes.id is None:
                continue
            boxes = r.boxes.xyxy.cpu().numpy() if hasattr(r.boxes.xyxy, "cpu") else r.boxes.xyxy
            ids = r.boxes.id.cpu().numpy().astype(int) if hasattr(r.boxes.id, "cpu") else r.boxes.id.astype(int)
            cls = r.boxes.cls.cpu().numpy() if hasattr(r.boxes.cls, "cpu") else r.boxes.cls

            for box, track_id, c in zip(boxes, ids, cls):
                if int(c) != 0:
                    continue
                cx = int((box[0] + box[2]) / 2)
                cy = int((box[1] + box[3]) / 2)
                centroid = (cx, cy)
                if not is_inside_roi(centroid, roi):
                    continue
                if track_id in self._prev_centroids:
                    crossing = detect_crossing(self._prev_centroids[track_id], centroid, line, direction)
                    if crossing:
                        crossings.append(crossing)
                self._prev_centroids[track_id] = centroid
        return crossings

    def _draw_overlays(self, frame, roi, line, direction):
        font = cv2.FONT_HERSHEY_SIMPLEX
        purple = (128, 0, 128)
        yellow = (0, 255, 255)

        # ROI polygon (purple, 2px)
        pts = np.array(roi, dtype=np.int32).reshape(-1, 1, 2)
        cv2.polylines(frame, [pts], True, purple, 2, cv2.LINE_AA)

        # "HUMAN DOOR" label with black background for readability
        xs = [p[0] for p in roi]
        ys = [p[1] for p in roi]
        min_x, min_y = min(xs), min(ys)
        label_y = max(min_y - 8, 20)
        (tw, th), _ = cv2.getTextSize("HUMAN DOOR", font, 0.6, 2)
        cv2.rectangle(frame, (min_x - 2, label_y - th - 4), (min_x + tw + 2, label_y + 4), (0, 0, 0), -1)
        cv2.putText(frame, "HUMAN DOOR", (min_x, label_y), font, 0.6, purple, 2)

        # Virtual counting line (yellow, 3px)
        cv2.line(frame, (line["x1"], line["y1"]), (line["x2"], line["y2"]), yellow, 3)
        mx = (line["x1"] + line["x2"]) // 2
        cv2.putText(frame, "COUNT LINE", (mx - 50, line["y1"] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        # Direction arrow
        my = line["y1"]

        # "VIRTUAL LINE" label centred above the line
        (vlw, _), _ = cv2.getTextSize("VIRTUAL LINE", font, 0.45, 1)
        cv2.putText(frame, "VIRTUAL LINE", (mx - vlw // 2, my - 10), font, 0.45, yellow, 1)

        # Direction arrow
        dmap = {"up": (0, -25), "down": (0, 25), "left": (-25, 0), "right": (25, 0)}
        dx, dy = dmap.get(direction, (0, -25))
        cv2.arrowedLine(frame, (mx, my), (mx + dx, my + dy), (0, 200, 0), 2, tipLength=0.4)

        # IN / OUT flanking labels (adapt to direction)
        in_label  = {"up": "^ IN",  "down": "v IN",  "left": "< IN",  "right": "> IN" }.get(direction, "IN")
        out_label = {"up": "v OUT", "down": "^ OUT", "left": "> OUT", "right": "< OUT"}.get(direction, "OUT")
        if direction in ("up", "down"):
            in_side  = (mx + 12, my + (20 if direction == "down" else -14))
            out_side = (mx + 12, my + (-14 if direction == "down" else 20))
        else:
            in_side  = (mx + (20 if direction == "right" else -60), my - 6)
            out_side = (mx + (-60 if direction == "right" else 20), my - 6)
        cv2.putText(frame, in_label,  in_side,  font, 0.45, (0, 220, 0), 1)
        cv2.putText(frame, out_label, out_side, font, 0.45, (100, 100, 255), 1)

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
