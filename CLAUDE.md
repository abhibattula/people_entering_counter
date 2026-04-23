# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan at:
specs/003-redesign-bugfix/plan.md

Also read:
- specs/003-redesign-bugfix/spec.md (feature specification)
- specs/003-redesign-bugfix/research.md (technical decisions)
- specs/003-redesign-bugfix/data-model.md (entity schemas)
- specs/003-redesign-bugfix/contracts/api.md (API contract delta)
- specs/003-redesign-bugfix/quickstart.md (setup guide)
- specs/001-doorway-people-counter/contracts/api.md (full base API contract)
- .specify/memory/constitution.md (project principles — binding)
<!-- SPECKIT END -->

---

## Commands

```bash
# Start the server (hot-reload enabled)
python run.py

# Run all tests
pytest

# Run unit tests only
pytest tests/unit/

# Run integration tests only
pytest tests/integration/

# Run a single test file
pytest tests/unit/test_quality_service.py -v

# Run with coverage
pytest --cov=backend tests/

# Enable debug logging
LOG_LEVEL=DEBUG python run.py

# Use a different camera
CAMERA_INDEX=1 python run.py

# Use a larger YOLO model (benchmarked justification required)
MODEL_VARIANT=yolov8s.pt python run.py
```

The app serves at **http://localhost:8000** after startup. YOLOv8n weights (~6MB) auto-download on first run.

---

## Architecture

**Runtime split**: Browser owns the camera during calibration (via `getUserMedia`). Python/OpenCV owns it during live counting. The handoff is a hard boundary — browser must call `stream.getTracks().forEach(t => t.stop())` before the counting route loads. Concurrent camera access is a constitution violation.

**Backend** (`backend/`): FastAPI app in `main.py`. Routers in `routers/` map 1:1 to API domains (calibration, profiles, sessions, stream, counts). Services in `services/` contain all domain logic:
- `model_service.py` — YOLOv8n singleton; patched in tests via `backend.services.model_service._model`
- `calibration_service.py` — two-stage doorway proposal (YOLO heatmap + OpenCV contours)
- `counting_service.py` — OpenCV capture loop with ByteTrack line-crossing detection
- `quality_service.py` — four placement heuristics (brightness, door visibility, crowding, distance)

**Database** (`backend/db/`): Raw `sqlite3` (no ORM). Schema and connection in `database.py`. Dataclasses in `models.py`. `SCHEMA_SQL` is exported from `database.py` and imported by `conftest.py` for in-memory test fixtures.

**Storage**: Door profiles as JSON in `backend/profiles/{uuid}.json`. Counting events in SQLite at `data/counts.db`. Both directories are gitignored and created at startup.

**Frontend** (`frontend/`): Plain HTML + vanilla JS. `index.html` = profile list, `calibrate.html` = 8-step photo-only wizard, `count.html` = live view. Served as static files by FastAPI. No build step.

**Live stream**: MJPEG over HTTP (`GET /stream?profile_id=...`). Rendered server-side with OpenCV overlays (ROI polygon, counting line, bounding boxes). Consumed by `<img src="...">` — no JS needed.

**Count events**: WebSocket at `WS /ws/counts?profile_id=...`. One JSON message per crossing: `{direction, occupancy, timestamp}`. Multiple tabs receive the same events from one counting loop.

**Logging**: Daily-rotating file at `logs/app.log`. Level from `LOG_LEVEL` env var (default INFO).

---

## Test Fixtures (conftest.py)

- `mem_db` — in-memory SQLite with full schema applied
- `mock_yolo` — `MagicMock` YOLO model with no detections
- `mock_yolo_with_person` — one centred person box `[200,100,440,460]`
- `client` — async `httpx.AsyncClient` patched against `backend.services.model_service._model`
- Frame helpers: `make_solid_frame`, `make_door_frame`, `make_gradient_frame`, `frames_to_jpeg_bytes`

Integration tests use `ASGITransport` (no real HTTP server). WebSocket tests use `httpx` WebSocket support.

---

## Constitution (binding)

The `.specify/memory/constitution.md` governs all implementation decisions. Key rules:

- **Spec-First**: No code before an approved spec entry. API contracts in `specs/.../contracts/api.md` are binding.
- **TDD mandatory**: Write failing tests before implementation. No task is complete unless all tests pass.
- **Single camera owner**: One process holds the camera at a time. OpenCV capture must close before returning control to browser.
- **No build step**: Vanilla JS only. Backend deps: `fastapi`, `uvicorn`, `ultralytics`, `opencv-python`, `aiofiles`. No ORMs. No new deps without written justification.
- **Commit format**: `type(scope): description` — types: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`
