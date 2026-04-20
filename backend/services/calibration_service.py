import base64
import cv2
import numpy as np
from typing import List

from backend.services.model_service import get_model

MAX_RETRIES = 2


class TooManyRetriesError(Exception):
    pass


class CalibrationSession:
    """Stateful per-calibration context tracking retry count."""

    def __init__(self):
        self._calls_made = 0

    @property
    def retry_count(self) -> int:
        """Number of retries used (0 = initial attempt only, 1 = one retry, etc.)."""
        return max(0, self._calls_made - 1)

    def propose(self, frames: List[np.ndarray], mode: str) -> dict:
        if self._calls_made > MAX_RETRIES:
            raise TooManyRetriesError("Maximum retries exceeded")
        result = propose_doorway(frames, mode)
        result["manual_fallback_available"] = self._calls_made >= MAX_RETRIES
        self._calls_made += 1
        return result


def propose_doorway(frames: List[np.ndarray], mode: str) -> dict:
    """
    Analyse captured frames and propose a doorway ROI, counting line, and
    inside direction. Returns the proposal dict (without manual_fallback_available).
    """
    h, w = frames[0].shape[:2]

    roi_polygon, confidence = _detect_roi(frames, w, h)
    counting_line = _midpoint_counting_line(roi_polygon)
    inside_direction = _infer_inside_direction(roi_polygon, w, h)
    best_frame = _pick_best_frame(frames)
    annotated = _annotate_frame(best_frame, roi_polygon, counting_line, inside_direction)
    b64 = base64.b64encode(annotated).decode()

    return {
        "roi_polygon": roi_polygon,
        "counting_line": counting_line,
        "inside_direction": inside_direction,
        "confidence": float(confidence),
        "best_frame_b64": b64,
    }


# ── ROI detection ─────────────────────────────────────────────────────────

def _detect_roi(frames: List[np.ndarray], w: int, h: int):
    """
    Use Canny edge detection + contour analysis to find the dominant
    rectangular region (the door frame). Falls back to a centred default.
    """
    best_contour = None
    best_area = 0
    confidence = 0.5

    for frame in frames:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 30, 100)
        dilated = cv2.dilate(edges, None, iterations=2)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            frame_area = w * h
            ratio = area / frame_area
            if 0.10 <= ratio <= 0.80 and area > best_area:
                best_area = area
                best_contour = cnt
                confidence = min(0.95, 0.5 + ratio)

    if best_contour is not None:
        hull = cv2.convexHull(best_contour)
        epsilon = 0.02 * cv2.arcLength(hull, True)
        approx = cv2.approxPolyDP(hull, epsilon, True)
        pts = approx.reshape(-1, 2).tolist()
        if len(pts) >= 4:
            pts = _order_quad(pts[:4])
            return pts, confidence

    # fallback: centred region covering ~40% of frame
    margin_x, margin_y = int(w * 0.25), int(h * 0.15)
    pts = [
        [margin_x,       margin_y],
        [w - margin_x,   margin_y],
        [w - margin_x,   h - margin_y],
        [margin_x,       h - margin_y],
    ]
    return pts, 0.3


def _order_quad(pts):
    """Order 4 points as top-left, top-right, bottom-right, bottom-left."""
    pts = sorted(pts, key=lambda p: p[1])  # sort by y
    top = sorted(pts[:2], key=lambda p: p[0])
    bottom = sorted(pts[2:], key=lambda p: p[0], reverse=True)
    return [top[0], top[1], bottom[0], bottom[1]]


# ── Counting line ─────────────────────────────────────────────────────────

def _midpoint_counting_line(roi_polygon) -> dict:
    """Horizontal line at the vertical midpoint of the ROI."""
    ys = [pt[1] for pt in roi_polygon]
    xs = [pt[0] for pt in roi_polygon]
    mid_y = int((min(ys) + max(ys)) / 2)
    return {"x1": int(min(xs)), "y1": mid_y, "x2": int(max(xs)), "y2": mid_y}


# ── Inside direction ──────────────────────────────────────────────────────

def _infer_inside_direction(roi_polygon, w: int, h: int) -> str:
    """
    Infer inside direction from where the ROI sits relative to the frame.
    ROI in upper half → inside is 'down'; lower half → 'up'.
    """
    ys = [pt[1] for pt in roi_polygon]
    cy = (min(ys) + max(ys)) / 2
    return "down" if cy < h / 2 else "up"


# ── Frame selection & annotation ──────────────────────────────────────────

def _pick_best_frame(frames: List[np.ndarray]) -> np.ndarray:
    """Return the frame with the highest contrast (std deviation of grey)."""
    scores = []
    for f in frames:
        gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        scores.append(float(np.std(gray)))
    return frames[int(np.argmax(scores))]


def _annotate_frame(frame: np.ndarray, roi_polygon, counting_line: dict, direction: str) -> bytes:
    """Draw ROI polygon + counting line + direction arrow on frame, encode as JPEG."""
    out = frame.copy()
    pts = np.array(roi_polygon, dtype=np.int32).reshape(-1, 1, 2)
    cv2.polylines(out, [pts], isClosed=True, color=(128, 0, 128), thickness=2)

    cv2.line(
        out,
        (counting_line["x1"], counting_line["y1"]),
        (counting_line["x2"], counting_line["y2"]),
        (0, 255, 255), 2,
    )

    # draw direction arrow at midpoint of counting line
    mx = (counting_line["x1"] + counting_line["x2"]) // 2
    my = counting_line["y1"]
    arrow_map = {"up": (0, -30), "down": (0, 30), "left": (-30, 0), "right": (30, 0)}
    dx, dy = arrow_map.get(direction, (0, -30))
    cv2.arrowedLine(out, (mx, my), (mx + dx, my + dy), (0, 200, 0), 2, tipLength=0.4)

    _, buf = cv2.imencode(".jpg", out)
    return buf.tobytes()
