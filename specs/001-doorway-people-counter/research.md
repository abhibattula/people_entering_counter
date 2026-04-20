# Research: Doorway People Counter

**Phase**: 0 — Research & Decisions
**Date**: 2026-04-20
**Feature**: [spec.md](./spec.md)

---

## Decision 1: ML Model — YOLOv8n via Ultralytics

**Decision**: Use `ultralytics` YOLOv8n (nano variant) for person detection.

**Rationale**:
- YOLOv8n is the fastest YOLOv8 variant; runs at 20–30 fps on mid-range CPU with ROI masking
- `ultralytics` bundles ByteTrack multi-object tracker — no separate tracking library needed
- Person class (class 0) detection is pre-trained and accurate at typical doorway scales (20–60% frame coverage)
- Single pip install; no CUDA required for CPU inference at these fps targets

**Alternatives considered**:
- MediaPipe: lighter but person detection less robust in partial occlusion
- OpenCV background subtraction: fast but fails with similar-coloured clothing and multi-person overlap
- YOLOv8s/m: more accurate but 2–3× slower; reserved as upgrade path if accuracy < 90%

---

## Decision 2: Multi-Object Tracking — ByteTrack (built-in)

**Decision**: Use ByteTrack via `model.track(source, tracker="bytetrack.yaml")`.

**Rationale**:
- ByteTrack is bundled in Ultralytics — zero extra dependencies
- Assigns persistent `track_id` per person across frames, enabling reliable line-crossing detection
- Works well at 10–30 fps even with brief occlusion (re-associates after 30-frame gap)
- Line-crossing logic: compare centroid position relative to counting line between consecutive frames per track_id

**Alternatives considered**:
- DeepSORT: better re-id after long occlusion but requires a reid model (extra dependency)
- Simple centroid tracker: would require writing tracking from scratch; ByteTrack is superior

---

## Decision 3: Video Streaming — MJPEG over HTTP

**Decision**: Serve annotated frames as MJPEG via `multipart/x-mixed-replace` at `GET /stream`.

**Rationale**:
- Works natively in `<img src="...">` — no JavaScript required for video display
- Supported by all modern browsers without plugins
- FastAPI + OpenCV frame encoding (`cv2.imencode('.jpg', frame)`) produces ~30KB/frame at 720p → ~300KB/s at 10fps — acceptable for localhost
- Annotations (ROI polygon, counting line, bounding boxes) rendered server-side via `cv2.draw*` — no canvas sync required

**Alternatives considered**:
- WebRTC: lowest latency but requires STUN/TURN infrastructure, complex signalling — overkill for localhost
- HLS: requires segment storage, higher latency, complex setup
- WebSocket binary frames: bidirectional but requires JS decode loop and canvas render

---

## Decision 4: Real-Time Count Events — WebSocket

**Decision**: Emit per-crossing JSON events via FastAPI WebSocket at `WS /ws/counts`.

**Rationale**:
- FastAPI has native WebSocket support via `websockets` (included in `uvicorn[standard]`)
- Allows instant counter updates independent of the MJPEG stream
- Event payload is tiny: `{"direction": "in", "occupancy": 5, "timestamp": "..."}` — no bandwidth concern
- Browser WebSocket API is natively supported with no library

**Alternatives considered**:
- Server-Sent Events (SSE): unidirectional, good for counts but no future bidirectional use (e.g., pause command)
- Polling: introduces latency; unsuitable for real-time display

---

## Decision 5: Doorway Boundary Proposal Algorithm

**Decision**: Two-stage proposal — YOLOv8 person heatmap + OpenCV contour detection.

**Rationale**:
- Stage 1: Run YOLOv8 person detection across all captured frames; accumulate bounding boxes; compute a density heatmap of where people appear
- Stage 2: Apply OpenCV Canny edge detection + Hough line transform on the best-lit frame to detect the door frame rectangle
- Merge: intersect person heatmap corridor with detected door rectangle → convex hull polygon = ROI proposal
- Counting line: horizontal midpoint of the ROI polygon (adjustable by user)
- Inside direction: inferred from room depth cues (blur/perspective) → user must confirm

**Alternatives considered**:
- Depth estimation (MiDaS): would give better inside/outside inference but adds a second model (~500MB) — too heavy for v1
- Manual-only: acceptable fallback but not the primary path

---

## Decision 6: Browser Camera Capture — getUserMedia + MediaRecorder

**Decision**: Use `getUserMedia({ video: { width: 1280, height: 720 } })` for preview and capture.

**Rationale**:
- Standard browser API, no polyfill needed for modern Chrome/Firefox
- Video mode: `MediaRecorder` records a 5-second `webm` blob; frames extracted by seeking a hidden `<video>` element and drawing to `<canvas>` at 15 evenly-spaced timestamps
- Photo mode: `canvas.drawImage(videoElement, ...)` → `canvas.toBlob('image/jpeg', 0.92)` per shot
- All frames collected into a `FormData` payload for `POST /api/calibrate/frames`
- Camera released via `stream.getTracks().forEach(t => t.stop())` before navigating to count view

**Alternatives considered**:
- Backend camera capture for calibration: would require Python to open/close camera twice; browser flow is smoother UX

---

## Decision 7: Placement Quality Heuristics

**Decision**: Assess four indicators from captured frames using OpenCV image analysis.

| Indicator | Method | Threshold |
|---|---|---|
| Door fully visible | Contour detection — door frame must reach ≥2 frame edges | Fail if <2 edges reached |
| Lighting acceptable | Mean frame brightness (LAB L-channel) | Fail if mean L < 60 or > 230 |
| Crowding risk | Count person detections per frame across all captured frames | Low <1.5 avg · Medium 1.5–3 · High >3 |
| Camera adjustment | Estimate door ROI area as % of frame | Too close >65% · Too far <15% · OK otherwise |

**Rationale**: These heuristics are fast (run on CPU in <500ms for 15 frames), require no additional models, and cover the four most common setup mistakes.

---

## Decision 8: Testing Strategy

**Decision**: pytest for all backend tests; split unit and integration.

**Unit tests** (mock camera + mock YOLOv8 model):
- `test_calibration_service.py`: doorway proposal algorithm with synthetic frames
- `test_counting_service.py`: line-crossing logic with synthetic centroid sequences
- `test_quality_service.py`: brightness/coverage/crowding heuristics with synthetic images
- `test_database.py`: session and event CRUD

**Integration tests** (real FastAPI test client, in-memory SQLite):
- `test_calibration_api.py`: POST frames → quality check + proposal response
- `test_profiles_api.py`: CRUD lifecycle
- `test_sessions_api.py`: start → events → export CSV
- `test_websocket_counts.py`: WebSocket connects, receives events when counting_service emits

**Fixtures** (`conftest.py`):
- Synthetic JPEG frames (solid colour, gradient) for deterministic quality tests
- Mock YOLOv8 model that returns configurable detection results
- In-memory SQLite database (`:memory:`) for all DB tests
- Test FastAPI app with counting_service stubbed out

**Rationale**: Full camera hardware is not available in CI; mocking YOLOv8 and OpenCV capture allows deterministic, fast tests without GPU or camera hardware.

---

## Resolved Clarifications

All technical unknowns resolved above. No NEEDS CLARIFICATION markers carried forward to Phase 1.
