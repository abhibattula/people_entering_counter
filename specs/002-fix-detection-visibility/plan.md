# Implementation Plan: Detection Accuracy & Visual Clarity Fixes

**Branch**: `002-fix-detection-visibility` | **Date**: 2026-04-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/002-fix-detection-visibility/spec.md`

---

## Summary

Fix 8 confirmed root-cause bugs in the existing doorway people counter and add four visual improvements. All changes are confined to existing backend service files, two routers, and the calibration/counting front-end JS. No new dependencies, no schema changes beyond one optional profile field, and no new API endpoints beyond an optional `grayscale` query parameter on the existing `/stream` route.

---

## Technical Context

**Language/Version**: Python 3.10+ (backend) · Vanilla JS/HTML/CSS (frontend)
**Primary Dependencies**: `fastapi`, `uvicorn[standard]`, `ultralytics` (YOLOv8 + ByteTrack), `opencv-python`, `aiofiles` — unchanged
**Storage**: JSON profiles (`backend/profiles/{uuid}.json`) · SQLite (`data/counts.db`) — no migration needed; one optional field added to profile JSON
**Testing**: `pytest` + `httpx` (async) · `pytest-asyncio` — existing suite extended
**Target Platform**: Local laptop (Windows/macOS/Linux) · modern Chromium/Firefox
**Project Type**: Local web-service + browser UI (hybrid desktop app)
**Performance Goals**: ≥10 fps maintained after fixes · grayscale mode reduces per-frame JPEG payload by ≥20%
**Constraints**: Fully offline · single command startup · no new dependencies · backward-compatible with existing profiles
**Scale/Scope**: Single user · single active camera · all fixes are additive or replace existing logic

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|---|---|---|
| I. Spec-First | ✅ PASS | `specs/002-fix-detection-visibility/spec.md` exists, fully populated, checklist passes |
| II. Local-Only, Zero Cloud | ✅ PASS | No new external calls; YOLO heatmap reuses the already-loaded local model singleton |
| III. Test-First (TDD) | ✅ PASS | Tests must be written and fail before each service function is changed; existing test suite provides baseline |
| IV. Single Camera Ownership | ✅ PASS | No changes to the camera handoff protocol; resolution fix is applied after `cv2.VideoCapture` opens, before the loop |
| V. Minimal Stack, No Build Step | ✅ PASS | Zero new dependencies; grayscale toggle uses existing OpenCV `cvtColor`; frontend remains vanilla JS |

**Gate result: ALL PASS — proceed to Phase 0.**

Post-design re-check: no violations introduced. No Complexity Tracking entries required.

---

## Project Structure

### Documentation (this feature)

```text
specs/002-fix-detection-visibility/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── api.md           # Phase 1 output — delta contract (stream grayscale param only)
└── tasks.md             # Phase 2 output (created by /speckit-tasks)
```

### Source Code (files changed by this feature)

```text
backend/
├── services/
│   ├── counting_service.py    # Bugs 1, 2, 7, 9, 10 — resolution, detection, fps, grayscale, labels
│   ├── calibration_service.py # Bugs 3, 4 — YOLO heatmap, polygon corners
│   └── quality_service.py     # Bug 8 — door visibility threshold
├── routers/
│   └── stream.py              # Bug 9 — grayscale query param forwarded to service

frontend/
├── js/
│   ├── calibrate.js           # Bug 5 (direction flip button), Bug 6 (manual draw UX)
│   └── count.js               # Bug 9 (grayscale toggle), visual label improvements
├── calibrate.html             # Bug 5 — "Flip direction" button in step 6

tests/
├── unit/
│   ├── test_counting_service.py    # New cases for resolution set, detection split, fps guard
│   ├── test_calibration_service.py # New cases for YOLO heatmap, polygon corner selection
│   └── test_quality_service.py     # New cases for tightened door visibility check
└── integration/
    └── test_stream_grayscale.py    # New — grayscale param on /stream endpoint
```

---

## Complexity Tracking

> No constitution violations — this section is intentionally empty.
