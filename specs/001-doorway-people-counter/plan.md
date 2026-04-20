# Implementation Plan: Doorway People Counter

**Branch**: `001-doorway-people-counter` | **Date**: 2026-04-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/001-doorway-people-counter/spec.md`

---

## Summary

Build a local browser-deployed people counter for doorways. A Python backend (FastAPI + YOLOv8 + OpenCV) handles ML inference, MJPEG streaming, and WebSocket count events. A Vanilla JS frontend handles camera permission, guided calibration, and the live counting view. Door profiles are stored as JSON; count history in SQLite. The system starts with a single command (`python run.py`) and requires no build step.

---

## Technical Context

**Language/Version**: Python 3.10+ (backend) · Vanilla JS/HTML/CSS (frontend, no transpilation)
**Primary Dependencies**: `fastapi`, `uvicorn[standard]`, `ultralytics` (YOLOv8 + ByteTrack), `opencv-python`, `aiofiles`, `python-multipart`
**Storage**: JSON files per door profile (`backend/profiles/{uuid}.json`) · SQLite via stdlib `sqlite3` (`data/counts.db`)
**Testing**: `pytest` + `httpx` (async FastAPI tests) · `pytest-asyncio` (WebSocket + stream tests) · manual browser testing for calibration wizard
**Target Platform**: Local laptop (Windows/macOS/Linux) · modern Chromium or Firefox (getUserMedia + MediaRecorder support required)
**Project Type**: local web-service + browser UI (hybrid desktop app)
**Performance Goals**: ≥10 fps inference during live counting · ≤1 s count display latency after crossing · ≤3 s MJPEG stream load on page open · ≤3 min first-time setup completion
**Constraints**: fully offline · single command startup · no frontend build step · single camera active at a time · doorway must cover 20–60% of frame
**Scale/Scope**: single user · single active camera · multiple saved profiles · up to ~100 crossing events per hour per session

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Evidence |
|---|---|---|
| I. Spec-First | ✅ PASS | `specs/001-doorway-people-counter/spec.md` exists, fully populated, quality checklist passes |
| II. Local-Only, Zero Cloud | ✅ PASS | All storage is local JSON + SQLite; YOLOv8 runs via Ultralytics locally; no external API calls |
| III. Test-First (TDD) | ✅ PASS | pytest suite planned; tests will be written before each service implementation |
| IV. Single Camera Ownership | ✅ PASS | Explicit browser→Python handoff at Step 9 of wizard; `getTracks().stop()` before OpenCV opens |
| V. Minimal Stack, No Build Step | ✅ PASS | Vanilla JS; `fastapi`, `ultralytics`, `opencv-python` only; `python run.py` startup |

**Gate result: ALL PASS — proceed to Phase 0.**

Post-design re-check: no violations introduced. No Complexity Tracking entries required.

---

## Project Structure

### Documentation (this feature)

```text
specs/001-doorway-people-counter/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── api.md           # Phase 1 output — full API contract
└── tasks.md             # Phase 2 output (created by /speckit-tasks)
```

### Source Code (repository root)

```text
doorway-counter/
├── backend/
│   ├── main.py                     # FastAPI app entry point
│   ├── config.py                   # paths, model variant, camera defaults
│   ├── routers/
│   │   ├── calibration.py          # POST /api/calibrate/frames, /retry
│   │   ├── profiles.py             # CRUD /api/profiles
│   │   ├── stream.py               # GET /stream (MJPEG)
│   │   ├── counts.py               # WS /ws/counts
│   │   └── sessions.py             # POST /api/sessions/*, GET /export
│   ├── services/
│   │   ├── model_service.py        # YOLOv8 singleton loader
│   │   ├── calibration_service.py  # frame analysis, ROI proposal
│   │   ├── counting_service.py     # OpenCV loop, ByteTrack, line crossing
│   │   └── quality_service.py      # placement quality heuristics
│   ├── db/
│   │   ├── database.py             # sqlite3 connection, CREATE TABLE
│   │   └── models.py               # Session, Event dataclasses
│   └── profiles/                   # gitignored JSON store
├── frontend/
│   ├── index.html                  # profile list home
│   ├── calibrate.html              # 9-step wizard
│   ├── count.html                  # live counting view
│   ├── js/
│   │   ├── calibrate.js            # wizard state machine, getUserMedia
│   │   ├── count.js                # MJPEG img swap, WebSocket client
│   │   ├── api.js                  # fetch wrapper
│   │   └── utils.js                # canvas drawing, quality badges
│   └── css/
│       └── styles.css
├── data/                           # gitignored SQLite
├── tests/
│   ├── unit/
│   │   ├── test_calibration_service.py
│   │   ├── test_counting_service.py
│   │   ├── test_quality_service.py
│   │   └── test_database.py
│   ├── integration/
│   │   ├── test_calibration_api.py
│   │   ├── test_profiles_api.py
│   │   ├── test_sessions_api.py
│   │   └── test_websocket_counts.py
│   └── conftest.py                 # shared fixtures, test DB, mock camera
├── requirements.txt
├── run.py
└── README.md
```

**Structure Decision**: Web application (Option 2) with backend/ and frontend/ separation. Tests live in a top-level `tests/` directory split into unit and integration suites. No `src/` nesting — files are shallow for a local tool of this scale.

---

## Complexity Tracking

> No constitution violations — this section is intentionally empty.
