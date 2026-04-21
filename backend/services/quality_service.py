import cv2
import numpy as np
from typing import List

from backend.services.model_service import get_model


def assess_quality(frames: List[np.ndarray]) -> dict:
    """
    Assess camera placement quality from captured frames.
    Returns all four placement quality indicators.
    """
    lighting = _check_lighting(frames)
    door_visible = _check_door_visibility(frames)
    crowding = _check_crowding_risk(frames)
    adjustment = _check_camera_adjustment(frames)

    return {
        "door_fully_visible": bool(door_visible),
        "lighting_acceptable": bool(lighting),
        "crowding_risk": crowding,
        "camera_adjustment": adjustment,
    }


# ── Lighting ──────────────────────────────────────────────────────────────

def _check_lighting(frames: List[np.ndarray]) -> bool:
    """Mean LAB L-channel brightness must be 60–230."""
    means = []
    for f in frames:
        lab = cv2.cvtColor(f, cv2.COLOR_BGR2LAB)
        means.append(float(np.mean(lab[:, :, 0])))
    avg = np.mean(means) if means else 0
    # LAB L channel ranges 0–255 in OpenCV
    return 60 <= avg <= 230


# ── Door visibility ───────────────────────────────────────────────────────

def _contour_touches_n_edges(contours, frame_shape, n: int = 2) -> bool:
    """Return True if any contour's bounding rect touches at least n frame edges."""
    h, w = frame_shape[:2]
    margin = 5
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        edges_touched = 0
        if x <= margin:
            edges_touched += 1
        if y <= margin:
            edges_touched += 1
        if x + cw >= w - margin:
            edges_touched += 1
        if y + ch >= h - margin:
            edges_touched += 1
        if edges_touched >= n:
            return True
    return False


def _check_door_visibility(frames: List[np.ndarray]) -> bool:
    """
    Door is visible when strong edges exist AND at least one contour covers
    ≥5% of the frame area (a real door frame) OR a contour spans ≥2 frame
    edges. This rejects blank walls (no edges), and interior grid patterns
    (many tiny contours, none large enough).
    """
    results = []
    for f in frames:
        gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_count = np.count_nonzero(edges)
        frame_area = f.shape[0] * f.shape[1]
        has_edges = edge_count > frame_area * 0.003
        if not has_edges:
            results.append(False)
            continue
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        has_large_contour = any(cv2.contourArea(c) >= frame_area * 0.05 for c in contours)
        touches_edges = _contour_touches_n_edges(contours, f.shape)
        results.append(has_large_contour or touches_edges)
    return bool(np.mean(results) > 0.5) if results else False


# ── Crowding risk ─────────────────────────────────────────────────────────

def _check_crowding_risk(frames: List[np.ndarray]) -> str:
    """Avg persons per frame: <1.5 = low · 1.5–3 = medium · >3 = high."""
    model = get_model()
    counts = []
    for f in frames:
        results = model(f, verbose=False)
        n_persons = 0
        for r in results:
            if hasattr(r, "boxes") and r.boxes is not None:
                cls = r.boxes.cls.cpu().numpy() if hasattr(r.boxes.cls, "cpu") else r.boxes.cls
                n_persons += int(np.sum(cls == 0))
        counts.append(n_persons)
    avg = np.mean(counts) if counts else 0
    if avg < 1.5:
        return "low"
    elif avg <= 3:
        return "medium"
    return "high"


# ── Camera adjustment ─────────────────────────────────────────────────────

def _check_camera_adjustment(frames: List[np.ndarray]) -> str:
    """
    Estimate ROI area by finding the largest bright/contrasting region.
    15–65% of frame area → keep; <15% → closer; >65% → farther.
    """
    ratios = []
    for f in frames:
        gray = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            ratios.append(0.0)
            continue
        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)
        frame_area = f.shape[0] * f.shape[1]
        ratios.append(area / frame_area)

    avg = np.mean(ratios) if ratios else 0
    if avg < 0.15:
        return "closer"
    elif avg > 0.65:
        return "farther"
    return "keep"
