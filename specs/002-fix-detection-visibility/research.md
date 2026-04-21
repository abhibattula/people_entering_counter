# Research: Detection Accuracy & Visual Clarity Fixes

**Phase**: 0 — Research & Decisions
**Date**: 2026-04-21
**Feature**: [spec.md](./spec.md)

---

## Decision 1: Camera Resolution Fix — `cv2.CAP_PROP_FRAME_WIDTH/HEIGHT`

**Decision**: After `cv2.VideoCapture(camera_index)` opens successfully, immediately call:
```python
cap.set(cv2.CAP_PROP_FRAME_WIDTH, profile["frame_width"])
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, profile["frame_height"])
```

**Rationale**:
- OpenCV opens a camera at its negotiated default (often 640×480 on Windows even for HD cameras). The profile stores `frame_width` and `frame_height` from the browser capture. Without aligning these, every ROI polygon coordinate is in browser-resolution space but applied to OpenCV-resolution frames, placing every centroid outside the ROI.
- `CAP_PROP_FRAME_WIDTH/HEIGHT` are standard OpenCV camera properties; the camera driver will round to the nearest supported resolution.
- If the driver cannot honour the requested resolution, OpenCV falls back gracefully to the nearest available size. A warning should be logged if the returned size does not match the requested size.

**Alternatives considered**:
- Scale the ROI polygon to match whatever OpenCV resolution is: rejected — adds complexity and accumulates rounding errors with no benefit over just setting the camera resolution.
- Store camera index per session and re-enumerate at start: rejected — profile already has all required metadata.

---

## Decision 2: Separate Detection Drawing from Tracking Gate

**Decision**: Split the inner loop in `counting_service._loop` into two passes:
1. **Detection pass** (no ID required): for every box returned by YOLO where `class == 0` (person) and centroid is inside ROI, draw a green bounding box. Use a lighter colour (e.g. `(0, 200, 0)`) when no track ID is available vs. full green `(0, 255, 0)` when tracked.
2. **Tracking pass** (ID required): only for boxes where `r.boxes.id is not None`, update `_prev_centroids` and check line crossing.

**Rationale**:
- ByteTrack assigns IDs based on motion continuity. In static or early frames `r.boxes.id` is `None`. The current code skips the entire result set including drawing. Users see nothing, making the system appear broken.
- Separating the passes means a person is always visible with a bounding box from the first frame YOLO detects them, even before ByteTrack assigns an ID.
- Line-crossing logic correctly requires a track ID and a previous centroid, so no phantom crossing events occur from untracked detections.

**Alternatives considered**:
- Assign a local provisional ID for untracked detections: rejected — provisional IDs could collide with ByteTrack IDs, causing false crossing events.
- Lower ByteTrack `track_thresh` to assign IDs faster: tested conceptually — may increase false tracks; cleaner to decouple display from tracking gate.

---

## Decision 3: YOLO Person-Density Heatmap for Door Detection

**Decision**: In `calibration_service._detect_roi`, before the Canny contour pass, run the loaded YOLO model on all captured frames and accumulate person bounding boxes into a binary occupancy mask. Then bias contour selection toward contours that overlap significantly with this mask.

Algorithm:
1. Create a zero-valued mask of frame size.
2. For each calibration frame, run `model(frame, verbose=False)`. For each detected person (class 0), fill the bounding box region in the mask with 1.
3. After all frames, blur the mask with a large kernel to get a smooth corridor.
4. For each candidate contour found by Canny, compute `overlap_ratio = (contour_area ∩ mask_area) / contour_area`.
5. Score each contour as `area_ratio * (1 + overlap_ratio)`. Select the highest-scoring contour.
6. Fall back to the previous Canny-only approach if no detections exist (empty doorway calibration).

**Rationale**:
- The existing algorithm picks the largest 10–80% contour regardless of where people walk. In a real room that is often a wall, window, or furniture.
- The person-density heatmap anchors the selection to where movement actually occurs, which is the doorway.
- Uses the already-loaded `get_model()` singleton — no extra model load.
- Graceful fallback when no people are detected in calibration frames.

**Alternatives considered**:
- Depth estimation (MiDaS) for better inside/outside inference: too heavy for v1 — adds ~500 MB model.
- Full image segmentation to find door-like rectangular structures: requires a custom-trained model.
- Hough line transform to find rectangle corners: already partially done via Canny + contours; adding the heatmap overlay is the minimal change that significantly improves accuracy.

---

## Decision 4: Correct Polygon Corner Selection

**Decision**: Replace the `pts[:4]` slice with proper 4-corner extraction using `cv2.minAreaRect`:

```python
rect = cv2.minAreaRect(best_contour)
box = cv2.boxPoints(rect)                         # 4 corners of minimum area rect
pts = box.astype(int).tolist()
pts = _order_quad(pts)                             # sort: TL, TR, BR, BL
```

**Rationale**:
- `cv2.approxPolyDP` returns points in contour traversal order. For a complex contour, the first 4 points are not guaranteed to be the 4 best corners.
- `cv2.minAreaRect` + `cv2.boxPoints` always returns exactly 4 corners of the smallest bounding rectangle, which is the correct geometric primitive for a doorway (a roughly rectangular opening).
- `_order_quad` remains unchanged and correctly sorts the 4 points.

**Alternatives considered**:
- Increase `epsilon` in `approxPolyDP` until exactly 4 points remain: fragile — epsilon value is contour-dependent and hard to tune across different doorway images.
- Manually pick 4 extreme corners (min-x, max-x, min-y, max-y combinations): valid but less robust than minAreaRect for tilted rectangles.

---

## Decision 5: User-Confirmed Inside Direction

**Decision**:
- Keep the existing `_infer_inside_direction` as a starting suggestion shown in the proposal step.
- Add a "Flip direction" button in step 6 of the calibration wizard (next to "Yes, this looks right").
- The `inside_direction` saved to the profile is whichever value the user has when they click "Yes" — either the inferred default or the flipped value.
- No new profile field needed: `inside_direction` already stores the value; the fix is ensuring the user can change it before confirming.

**Rationale**:
- The inferred direction (based on ROI vertical position) is correct ~50% of the time. Forcing the user to always set it manually adds friction.
- Allowing a "flip" with one click gives full control without requiring a full manual override flow.
- The profile JSON schema is unchanged.

**Alternatives considered**:
- Show a preview animation of people walking in both directions: good UX but out of scope for this bugfix sprint.
- Ask the user explicitly "which side is the interior?" as a text question: adds a step to the wizard.

---

## Decision 6: Manual Draw Canvas UX Fixes

**Decision**: Three targeted changes to `calibrate.js`:

1. **Store background image reference** in a module-level variable (`let drawBgImage = null`). In `startManualDraw`, assign `drawBgImage = img` after `img.onload`. In `redrawManual`, always: `ctx.clearRect(0,0,canvas.width,canvas.height)` then `ctx.drawImage(drawBgImage, 0,0)` before drawing any markers.

2. **Replace 5px arc dots with numbered circles**: Each marker is a filled circle (radius 14px) with a white outline (2px stroke) and the corner number (1–4) as centred white text. This is visible on any background.

3. **Progress label**: Add a `<p id="draw-progress">Tap corner 1 of 4</p>` element above the canvas in step 7 HTML. Update it after each click: "Tap corner N of 4" for N < 4, "Corners placed — click Save →" when all 4 are placed.

**Rationale**:
- Not clearing/redrawing the background before adding markers is the root cause of the "nothing happens" perception: after reset the background image disappears leaving only dots.
- 5px dots in purple are invisible on complex real-world backgrounds.
- No progress text means users don't know if their click registered.

**Alternatives considered**:
- SVG overlay for markers instead of canvas drawing: adds complexity, not needed.
- Draggable handles after placement: good UX improvement but out of scope for this fix.

---

## Decision 7: FPS Division-by-Zero Guard

**Decision**: In `CountingService.get_fps`:

```python
def get_fps(self) -> float:
    d = self._frame_times
    if len(d) >= 2 and d[-1] != d[0]:
        return (len(d) - 1) / (d[-1] - d[0])
    return 0.0
```

**Rationale**:
- `d[-1] == d[0]` when all buffered frames share the same timestamp (bursted delivery or mocked time). Current code raises `ZeroDivisionError` which kills the background thread silently — the stream freezes with no error.
- Also fixes the formula: the number of intervals is `len(d) - 1`, not `len(d)`.

**Alternatives considered**:
- `try/except ZeroDivisionError`: valid but hides the logic flaw; explicit guard is clearer.

---

## Decision 8: Door Visibility Quality Check Tightening

**Decision**: Replace the edge-pixel-count threshold with a two-condition check:

```python
# Condition 1: sufficient edge pixels (existing)
has_edges = avg_edges > frame_area * 0.003

# Condition 2: at least one contour touches ≥2 frame edges
contours, _ = cv2.findContours(edges_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
touches_edges = _contour_touches_n_edges(contours, frame, n=2)

return has_edges and touches_edges
```

Where `_contour_touches_n_edges` checks whether any contour's bounding box touches the left, right, top, or bottom edge of the frame.

**Rationale**:
- A door frame typically extends from one side of the frame to another (wall-to-wall). A plain white wall has edges everywhere but no single contour reaching 2 frame boundaries.
- This adds one CV operation (already using `cv2`) and no new dependencies.

**Alternatives considered**:
- Higher edge pixel threshold (e.g., 2%): still passes for blank walls.
- YOLO person detection as a proxy for door visibility: adds latency to the quality check.

---

## Decision 9: Grayscale Mode

**Decision**: 
- Backend: `CountingService` gains a `_grayscale: bool` flag (default `False`). When True, after `_draw_overlays` runs on the annotated frame, convert the frame to grayscale and back to BGR before JPEG encoding: `annotated = cv2.cvtColor(cv2.cvtColor(annotated, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)`. Overlays (purple, yellow, green) remain visible because they are applied before conversion.
- The `/stream` endpoint accepts an optional `?grayscale=true` query parameter and calls `svc.set_grayscale(True)` on the running service.
- Frontend: a "🔲 Grayscale" toggle button in `count.html` reloads the `<img src>` URL with `&grayscale=true` appended.

**Rationale**:
- Converting BGR → GRAY → BGR after overlays preserves annotation visibility while reducing per-channel variation that inflates JPEG size.
- A grayscale JPEG is still 3-channel BGR but with R=G=B per pixel; OpenCV handles this natively.
- The reload-on-toggle approach is simple and requires no WebSocket signalling.

**Alternatives considered**:
- Process frames in grayscale from the start: breaks overlay colour coding.
- Per-frame grayscale negotiation over WebSocket: over-engineered for a UI toggle.

---

## Decision 10: Visual Overlay Improvements

**Decision**: In `counting_service._draw_overlays`:

1. **Door label**: After drawing the ROI polygon, add:
   ```python
   xs = [p[0] for p in roi]
   ys = [p[1] for p in roi]
   label_x, label_y = min(xs), min(ys) - 8
   cv2.putText(frame, "DOOR", (label_x, max(label_y, 15)),
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (128, 0, 128), 2)
   ```

2. **Thicker counting line** (thickness 3 → was 2):
   ```python
   cv2.line(frame, (line["x1"], line["y1"]), (line["x2"], line["y2"]), (0, 255, 255), 3)
   ```

3. **COUNT LINE label** at line midpoint:
   ```python
   mx = (line["x1"] + line["x2"]) // 2
   cv2.putText(frame, "COUNT LINE", (mx - 50, line["y1"] - 8),
               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
   ```

**Rationale**: Minimal changes, visible results, no new dependencies.

---

## Resolved Clarifications

All technical unknowns resolved. No NEEDS CLARIFICATION markers carried forward.
