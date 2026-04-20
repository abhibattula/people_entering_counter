# Tasks: Doorway People Counter

**Input**: Design documents from `specs/001-doorway-people-counter/`
**Prerequisites**: plan.md ✅ · spec.md ✅ · research.md ✅ · data-model.md ✅ · contracts/api.md ✅
**TDD**: Test tasks are REQUIRED per constitution Principle III (Test-First, NON-NEGOTIABLE)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Maps to user story from spec.md (US1–US6)
- All file paths are relative to repo root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Lay down the project skeleton before any feature work begins.

- [ ] T001 Create full project directory structure: `backend/routers/`, `backend/services/`, `backend/db/`, `backend/profiles/`, `frontend/js/`, `frontend/css/`, `data/`, `tests/unit/`, `tests/integration/`, `logs/`
- [ ] T002 Create `requirements.txt` with: `fastapi`, `uvicorn[standard]`, `ultralytics`, `opencv-python`, `aiofiles`, `python-multipart`, `pytest`, `httpx`, `pytest-asyncio`
- [ ] T003 [P] Create `run.py` — single-command launcher: `uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload`
- [ ] T004 [P] Create `.gitignore` with entries: `backend/profiles/`, `data/`, `logs/`, `.superpowers/`, `__pycache__/`, `*.pyc`, `.env`
- [ ] T005 [P] Create `tests/conftest.py` — shared fixtures: in-memory SQLite DB, mock YOLOv8 model returning configurable detections, synthetic JPEG frames (solid colour + gradient), mock OpenCV capture

**Checkpoint**: Directory skeleton exists, dependencies listed, test fixtures ready.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before any user story begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T006 Create `backend/config.py` — centralised settings: `PROFILES_DIR`, `DB_PATH`, `LOGS_DIR`, `MODEL_VARIANT` (default `yolov8n`), `CAMERA_INDEX` (default 0), `HOST`, `PORT`
- [ ] T007 Write unit tests in `tests/unit/test_database.py` — verify: session CRUD, event insert, orphan-session auto-close on init, occupancy floor constraint. **Run and confirm FAIL.**
- [ ] T008 Create `backend/db/models.py` — `Session` and `CrossingEvent` dataclasses matching data-model.md schema
- [ ] T009 Create `backend/db/database.py` — sqlite3 connection, `CREATE TABLE IF NOT EXISTS` for `sessions` and `events` with indices, `close_orphaned_sessions()` called on module import (FR-021)
- [ ] T010 Run `tests/unit/test_database.py` and confirm all tests pass ✅
- [ ] T011 [P] Write unit tests in `tests/unit/test_model_service.py` — verify: singleton loads once, subsequent calls return same instance, mock load path works. **Run and confirm FAIL.**
- [ ] T012 [P] Create `backend/services/model_service.py` — YOLOv8 singleton: load `ultralytics.YOLO(config.MODEL_VARIANT)` once at module level; expose `get_model()` returning the shared instance
- [ ] T013 Run `tests/unit/test_model_service.py` and confirm all tests pass ✅
- [ ] T014 Create `backend/main.py` — FastAPI app: mount `StaticFiles` for `frontend/` at `/`, include all routers (registered in later phases), configure `logging` with `RotatingFileHandler` to `logs/app.log` (INFO default, `LOG_LEVEL` env var override) (FR-022)
- [ ] T015 Create `frontend/css/styles.css` — base layout: CSS variables for colours, wizard step container, count bar grid, video aspect-ratio wrapper, quality badge styles, error banner styles

**Checkpoint**: DB layer tested ✅ · model singleton tested ✅ · FastAPI app boots · logging configured · base CSS exists.

---

## Phase 3: User Story 1 — First-Time Door Setup (Priority: P1) 🎯 MVP

**Goal**: A user completes the full 9-step calibration wizard and sees their first live IN/OUT count.

**Independent Test**: Run `python run.py`, open `http://localhost:8000`, complete calibration with a webcam pointed at a doorway, confirm IN/OUT counters increment when someone crosses.

### Tests for US1 — Write FIRST, verify FAIL before implementing

- [ ] T016 [P] [US1] Write `tests/unit/test_quality_service.py` — test all 4 quality indicators: dark frame → lighting fail, clipped frame → door not visible, ROI <15% → farther, ROI >65% → closer, valid frame → all pass. **Run and confirm FAIL.**
- [ ] T017 [P] [US1] Write `tests/unit/test_calibration_service.py` — test proposal generation with synthetic frames: detects ROI polygon, counting line at midpoint, returns confidence score. **Run and confirm FAIL.**
- [ ] T018 [P] [US1] Write `tests/unit/test_counting_service.py` — test line-crossing logic: centroid moves from above to below line → "in", below to above → "out", stays same side → no event, occupancy floor at 0. **Run and confirm FAIL.**
- [ ] T019 [P] [US1] Write `tests/integration/test_calibration_api.py` — POST 5 synthetic JPEG frames to `/api/calibrate/frames` → assert 200, quality_check present, proposal has roi_polygon + counting_line + inside_direction. **Run and confirm FAIL.**
- [ ] T020 [P] [US1] Write `tests/integration/test_profiles_api.py` — test full CRUD: POST → 201, GET list → 200, GET by id → 200, DELETE → 204, GET after delete → 404. **Run and confirm FAIL.**

### Implementation for US1

- [ ] T021 [US1] Implement `backend/services/quality_service.py` — `assess_quality(frames: list[np.ndarray]) -> dict`: brightness check (LAB L-channel mean), door-visibility check (contour reaches ≥2 frame edges), crowding-risk count (avg YOLOv8 person detections per frame), ROI-size percentage check
- [ ] T022 [US1] Run `tests/unit/test_quality_service.py` and confirm all tests pass ✅
- [ ] T023 [US1] Implement `backend/services/calibration_service.py` — `propose_doorway(frames, mode) -> CalibrationProposal`: run YOLOv8 across frames, accumulate person heatmap, apply Canny + Hough on best frame, compute convex hull ROI, set counting line at horizontal midpoint, infer `inside_direction` from perspective cues, encode best frame as base64 JPEG with overlay
- [ ] T024 [US1] Run `tests/unit/test_calibration_service.py` and confirm all tests pass ✅
- [ ] T025 [US1] Implement `backend/routers/calibration.py` — `POST /api/calibrate/frames` and `POST /api/calibrate/retry`: receive multipart frames, call `quality_service.assess_quality()` then `calibration_service.propose_doorway()`, return combined response
- [ ] T026 [US1] Run `tests/integration/test_calibration_api.py` and confirm all tests pass ✅
- [ ] T027 [US1] Implement `backend/routers/profiles.py` — `GET /api/profiles`, `POST /api/profiles` (validate + write JSON to `backend/profiles/{uuid}.json`), `GET /api/profiles/{id}`, `DELETE /api/profiles/{id}` (also deletes associated SQLite events)
- [ ] T028 [US1] Run `tests/integration/test_profiles_api.py` and confirm all tests pass ✅
- [ ] T029 [US1] Implement `backend/services/counting_service.py` — `CountingService` class: `start(profile_id)` opens `cv2.VideoCapture`, runs YOLOv8n ByteTrack inference loop in background thread, applies ROI mask, detects line crossings per track_id, emits `CrossingEvent` to an asyncio queue; `stop()` closes camera; MJPEG frame generator method; `get_fps()` for health display
- [ ] T030 [US1] Run `tests/unit/test_counting_service.py` and confirm all tests pass ✅
- [ ] T031 [US1] Implement `backend/routers/stream.py` — `GET /stream?profile_id=`: start `CountingService` if not running, yield MJPEG frames as `multipart/x-mixed-replace`; return 503 if camera unavailable
- [ ] T032 [P] [US1] Implement `backend/routers/counts.py` — `WS /ws/counts?profile_id=`: accept WebSocket, subscribe to `CountingService` event queue, forward `{"direction","occupancy","timestamp"}` JSON per crossing; handle disconnect cleanly (FR-023: multiple clients supported)
- [ ] T033 [P] [US1] Implement `backend/routers/sessions.py` (start/end only) — `POST /api/sessions/start` creates session row, `POST /api/sessions/{id}/end` sets `ended_at`; wire `CountingService` to write `CrossingEvent` rows on each crossing
- [ ] T034 [P] [US1] Write `tests/integration/test_websocket_counts.py` — connect WebSocket, trigger mock crossing event from `CountingService`, assert JSON message received with correct shape. **Run, implement any fixes, confirm pass ✅**
- [ ] T035 [US1] Create `frontend/index.html` — profile list home page: empty-state prompt ("No doors yet — Create one"), profile cards (name + created date), "Create New Door/Entryway Profile" button; calls `GET /api/profiles` on load
- [ ] T036 [US1] Create `frontend/js/api.js` — fetch wrapper: `getProfiles()`, `createProfile(data)`, `getProfile(id)`, `deleteProfile(id)`, `startSession(profileId)`, `endSession(id)`, `startCalibration(frames, mode)`, `retryCalibration(frames, mode)`
- [ ] T037 [US1] Create `frontend/js/utils.js` — canvas helpers: `drawPolygon(ctx, points, colour)`, `drawLine(ctx, line, colour)`, `drawArrow(ctx, x, y, direction)`, `drawBoundingBox(ctx, box)`, `renderQualityBadges(container, qualityCheck)`
- [ ] T038 [US1] Create `frontend/calibrate.html` — 9-step wizard scaffold: step containers (hidden by default), progress indicator, step nav buttons; `<video>` element for live preview, `<canvas>` for overlay drawing
- [ ] T039 [US1] Create `frontend/js/calibrate.js` — wizard state machine: steps 1–9 (camera permission → preview → mode select → capture → quality check → proposal display → confirmation → door-behaviour question → save); `getUserMedia`, `canvas.drawImage` for photo capture, `stopTracks()` before navigating to count view
- [ ] T040 [US1] Create `frontend/count.html` — live counting view: `<img id="stream">` MJPEG target, count bar (IN / OUT / OCCUPANCY), recent-events log, Pause/Reset/Stop controls, Recalibrate + Export CSV + Switch Door buttons
- [ ] T041 [US1] Create `frontend/js/count.js` — set `img.src = /stream?profile_id=...`, open WebSocket `/ws/counts?profile_id=...`, update DOM on each event, handle reconnect with 3 s backoff, stale-stream reload on `img.onerror`

**Checkpoint**: Full calibration wizard runs end-to-end in browser. Live counting view shows MJPEG stream with IN/OUT counts updating in real time. ✅ MVP complete.

---

## Phase 4: User Story 2 — Video Clip Capture Mode (Priority: P2)

**Goal**: User completes calibration using the 5-second video clip path instead of guided photos.

**Independent Test**: Select "5-second video clip" at mode selection, complete capture + calibration, reach live counting — without using photo mode at all.

### Tests for US2 — Write FIRST, verify FAIL

- [ ] T042 [P] [US2] Write `tests/integration/test_calibration_api.py` (video mode case) — POST 15 JPEG frames with `mode=video` → assert same 200 response shape as photo mode. **Run and confirm FAIL.**

### Implementation for US2

- [ ] T043 [US2] Update `frontend/js/calibrate.js` — add video mode branch in step 4: initialise `MediaRecorder` on the `getUserMedia` stream, show 3-2-1 countdown overlay, record 5 s `webm` blob, seek hidden `<video>` element at 15 evenly-spaced timestamps drawing each to canvas → `toBlob('image/jpeg')`, collect 15 frames, POST to `/api/calibrate/frames` with `mode=video`
- [ ] T044 [US2] Run `tests/integration/test_calibration_api.py` (video mode) and confirm pass ✅

**Checkpoint**: Both capture modes (photo + video) reach the same proposal screen. ✅

---

## Phase 5: User Story 3 — Placement Quality Feedback (Priority: P2)

**Goal**: Quality indicators (door visible, lighting, crowding, camera distance) are clearly displayed after capture and before the doorway proposal, with a Re-capture option.

**Independent Test**: Simulate a poorly-lit frame set → quality check shows "Lighting: No" + Re-capture button prominently before any proposal is shown.

### Tests for US3 — Write FIRST, verify FAIL

- [ ] T045 [P] [US3] Write `tests/unit/test_quality_service.py` (extended) — add edge-case tests: all-black frame, all-white frame, door at extreme corners. **Run and confirm FAIL.**

### Implementation for US3

- [ ] T046 [US3] Update `backend/services/quality_service.py` — add edge-case handling for extreme brightness and door at frame corners; ensure all 4 indicators always return valid values even on degenerate frames
- [ ] T047 [US3] Update `frontend/js/calibrate.js` step 5 — render `renderQualityBadges()` with colour-coded pass/fail for each indicator; show "Re-capture" button if any critical check fails (`door_fully_visible: false` or `lighting_acceptable: false`); show "Continue anyway" for non-critical warnings
- [ ] T048 [US3] Run `tests/unit/test_quality_service.py` (extended) and confirm all tests pass ✅

**Checkpoint**: Quality check screen shows actionable, colour-coded indicators before proposal is displayed. ✅

---

## Phase 6: User Story 4 — Proposal Rejection and Manual Fallback (Priority: P3)

**Goal**: When auto-proposal is rejected twice, the user can draw the doorway boundary and counting line manually on canvas.

**Independent Test**: Click "No" on a proposal twice — manual draw mode unlocks; drag polygon corners and reposition line; save profile and reach live counting.

### Tests for US4 — Write FIRST, verify FAIL

- [ ] T049 [P] [US4] Write `tests/unit/test_calibration_service.py` (retry tracking) — call `propose_doorway` 3 times, assert retry count increments and `manual_fallback_available` is true after 2 rejections. **Run and confirm FAIL.**

### Implementation for US4

- [ ] T050 [US4] Update `backend/services/calibration_service.py` — track retry count per request session; expose `manual_fallback_available: bool` in proposal response after 2 retries
- [ ] T051 [US4] Update `backend/routers/calibration.py` — `POST /api/calibrate/retry` returns 429 if retry count > 2; include `manual_fallback_available: true` in response body after 2nd retry
- [ ] T052 [US4] Update `frontend/js/calibrate.js` step 7 — track rejection count; on 2nd rejection show "Draw manually" button alongside retry; draw mode: render polygon with draggable corner handles on canvas using `utils.js` helpers, allow counting line repositioning via drag; "Save this boundary" button captures final canvas coordinates
- [ ] T053 [US4] Run `tests/unit/test_calibration_service.py` (retry tracking) and confirm pass ✅

**Checkpoint**: Manual fallback is fully functional. Users who reject auto-proposals can still set up a profile. ✅

---

## Phase 7: User Story 5 — Returning User Loads Existing Profile (Priority: P2)

**Goal**: Saved profiles listed on home screen; clicking one starts a new counting session within 3 seconds.

**Independent Test**: Create a profile, stop the session, refresh the page — profile appears in the list; clicking it starts counting immediately with the saved boundary applied.

### Tests for US5 — Write FIRST, verify FAIL

- [ ] T054 [P] [US5] Write `tests/integration/test_profiles_api.py` (list + load) — create 2 profiles, GET `/api/profiles` → assert 2 items with name + created_at; GET `/api/profiles/{id}` → assert full profile fields present. **Run and confirm FAIL (list test may already pass — verify full field set).**
- [ ] T055 [P] [US5] Write `tests/integration/test_sessions_api.py` — `POST /api/sessions/start` → 201 with session_id; `POST /api/sessions/{id}/end` → 204; `GET /api/sessions/{id}/events` → empty list. **Run and confirm FAIL.**

### Implementation for US5

- [ ] T056 [US5] Update `frontend/index.html` — replace static empty-state with dynamic profile card rendering from `GET /api/profiles`; each card shows name, created date, "Start Counting" button; "Delete" button with confirmation dialog
- [ ] T057 [US5] Update `frontend/js/count.js` — on page load read `?profile_id=` param, call `POST /api/sessions/start`, apply saved `roi_polygon` and `counting_line` overlay on canvas over the MJPEG `<img>`, show `door_randomly_opens` warning banner if set in profile (FR-010)
- [ ] T058 [US5] Run `tests/integration/test_profiles_api.py` (list + load) and confirm pass ✅
- [ ] T059 [US5] Run `tests/integration/test_sessions_api.py` and confirm pass ✅
- [ ] T060 [P] [US5] Implement `GET /api/health` in `backend/main.py` — return `model_loaded`, `camera_available` (probe `cv2.VideoCapture(config.CAMERA_INDEX)` and release), `status: "ok"|"degraded"`
- [ ] T061 [P] [US5] Implement `GET /api/cameras` in `backend/main.py` — probe indices 0–4, return list of available cameras with index, resolution

**Checkpoint**: Returning users see their profiles, load them in <3 s, and counting begins immediately. Health + camera discovery endpoints working. ✅

---

## Phase 8: User Story 6 — Session Export and History (Priority: P3)

**Goal**: Users can export a session's crossing events as CSV and view session history per profile.

**Independent Test**: Complete a session with ≥5 crossings, click "Export CSV", download opens correctly in a spreadsheet with correct columns and timestamps.

### Tests for US6 — Write FIRST, verify FAIL

- [ ] T062 [P] [US6] Write `tests/integration/test_sessions_api.py` (export) — insert 3 events via DB directly, call `GET /api/sessions/{id}/export` → assert `Content-Disposition: attachment`, CSV has header row + 3 data rows with correct columns. **Run and confirm FAIL.**
- [ ] T063 [P] [US6] Write `tests/integration/test_profiles_api.py` (export/import) — export a profile via `GET /api/profiles/{id}/export` → download JSON; POST JSON to `/api/profiles/import` → 201 with new id; GET new id → all fields match original except id. **Run and confirm FAIL.**

### Implementation for US6

- [ ] T064 [US6] Update `backend/routers/sessions.py` — add `GET /api/sessions/{id}/events` (list events) and `GET /api/sessions/{id}/export` (stream CSV with `Content-Disposition: attachment; filename="session-{id}.csv"`)
- [ ] T065 [US6] Update `backend/routers/profiles.py` — add `GET /api/profiles/{id}/export` (download profile JSON as attachment) and `POST /api/profiles/import` (validate schema, assign new UUID, write to profiles dir) (FR-024)
- [ ] T066 [US6] Update `frontend/js/count.js` — wire "Export CSV" button to `GET /api/sessions/{id}/export` using a temporary `<a>` download link
- [ ] T067 [US6] Update `frontend/index.html` — add "Session History" section per profile: fetch sessions for selected profile, list each with start/end time, total IN, total OUT, download link (FR-018); add "Import Profile" button wired to file-input → `POST /api/profiles/import`
- [ ] T068 [US6] Run `tests/integration/test_sessions_api.py` (export) and confirm pass ✅
- [ ] T069 [US6] Run `tests/integration/test_profiles_api.py` (export/import) and confirm pass ✅

**Checkpoint**: Session CSV export working. Profile export/import working. Session history visible per profile. ✅

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Hardening, error UX, and quickstart validation across all stories.

- [ ] T070 [P] Implement WebSocket auto-reconnect in `frontend/js/count.js` — on `onclose`/`onerror`, retry with 3 s backoff (max 5 attempts), show "Reconnecting…" banner; clear banner on successful reconnect
- [ ] T071 [P] Implement MJPEG stale-stream recovery in `frontend/js/count.js` — on `img.onerror`, reload `src` with `?ts=Date.now()` cache-bust after 2 s; show "Stream interrupted" badge
- [ ] T072 [P] Add FPS display to MJPEG stream — `counting_service.get_fps()` rendered server-side on each frame via `cv2.putText`; also show `model_variant` label
- [ ] T073 [P] Add camera-error handling in `backend/routers/stream.py` — if `cv2.VideoCapture` fails to open, return 503 JSON; browser shows actionable "Camera unavailable" overlay with retry button
- [ ] T074 Add camera-deny UX in `frontend/js/calibrate.js` step 1 — catch `getUserMedia` `NotAllowedError`; show instructions panel with browser-specific steps to re-enable camera permission
- [ ] T075 [P] Register `logs/` directory creation in `backend/main.py` startup event — `Path("logs").mkdir(exist_ok=True)` so first run never fails due to missing dir
- [ ] T076 [P] Add `README.md` with quickstart instructions mirroring `specs/001-doorway-people-counter/quickstart.md`
- [ ] T077 Run full test suite `pytest --tb=short` — confirm all unit + integration tests pass, fix any regressions ✅
- [ ] T078 Manual end-to-end walkthrough per `specs/001-doorway-people-counter/quickstart.md` — complete all 10 verification checklist items, document any deviations

**Checkpoint**: All 78 tasks complete. Full test suite green. Quickstart validation passed. ✅

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (US1)**: Depends on Phase 2 — 🎯 MVP target; must complete before all others
- **Phase 4 (US2)**: Depends on Phase 3 (reuses calibrate.js wizard skeleton)
- **Phase 5 (US3)**: Depends on Phase 3 (refines quality_service + step 5 UI)
- **Phase 6 (US4)**: Depends on Phase 3 (extends calibration retry flow)
- **Phase 7 (US5)**: Depends on Phase 3 (reuses profiles API + count.js)
- **Phase 8 (US6)**: Depends on Phase 7 (extends sessions API + index.html)
- **Phase 9 (Polish)**: Depends on all phases complete

### User Story Dependencies

| Story | Depends On | Can Parallelise With |
|---|---|---|
| US1 (P1) | Phase 2 only | — |
| US2 (P2) | US1 | US3, US5 |
| US3 (P2) | US1 | US2, US5 |
| US4 (P3) | US1 | US5 |
| US5 (P2) | US1 | US2, US3, US4 |
| US6 (P3) | US5 | US4 |

### Parallel Opportunities Within US1

```
# Run these test tasks in parallel (T016–T020):
T016 test_quality_service.py (write + fail)
T017 test_calibration_service.py (write + fail)
T018 test_counting_service.py (write + fail)
T019 test_calibration_api.py (write + fail)
T020 test_profiles_api.py (write + fail)

# Run these service implementations in parallel (T021, T023):
T021 quality_service.py
T023 calibration_service.py (after T022 passes)

# Run these endpoint implementations in parallel (T031, T032, T033):
T031 stream.py
T032 counts.py
T033 sessions.py (start/end)

# Run these frontend files in parallel (T036, T037):
T036 api.js
T037 utils.js
```

---

## Implementation Strategy

### MVP First (US1 Only — Phases 1–3)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (tests pass ✅)
3. Complete Phase 3: US1 (tests pass ✅)
4. **STOP and VALIDATE**: Manual walkthrough — calibration wizard + live counting works end-to-end
5. Demo / validate before proceeding to P2/P3 stories

### Incremental Delivery

1. Phase 1 + 2 → Foundation tested ✅
2. Phase 3 (US1) → MVP: setup + counting working ✅
3. Phase 4 (US2) + Phase 5 (US3) in parallel → Both capture modes + quality UX ✅
4. Phase 6 (US4) + Phase 7 (US5) in parallel → Manual fallback + returning-user flow ✅
5. Phase 8 (US6) → Export + history ✅
6. Phase 9 → Polish + full test suite green ✅

---

## Notes

- `[P]` tasks touch different files and have no dependencies on incomplete tasks in the same phase
- TDD is NON-NEGOTIABLE per constitution Principle III — every "Write tests … FAIL" step must be verified before implementing
- Commit after each checkpoint (end of each phase)
- Camera hardware not available in CI — use mock fixtures from `conftest.py` for all automated tests
- Manual verification steps (quickstart.md walkthrough) cannot be automated — document results in commit message
