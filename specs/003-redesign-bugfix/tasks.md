# Tasks: UI Redesign, Bug Fixes & Video Mode Removal

**Input**: Design documents from `specs/003-redesign-bugfix/`
**Prerequisites**: plan.md ✅ · spec.md ✅ · research.md ✅ · data-model.md ✅ · contracts/api.md ✅

**TDD Note**: Per the project constitution (Principle III), tests MUST be written and confirmed to FAIL before any implementation task begins. Each test task below was completed before the implementation tasks it precedes.

**Format**: `[ID] [P?] [Story?] Description with file path`
- **[P]**: Parallelisable (touches different files, no cross-task dependency)
- **[Story]**: User Story that this task serves

---

## Phase 1: Setup

**Purpose**: Confirm the existing test suite is green before any changes are made.

- [x] T001 Run `pytest` and confirm all existing tests pass; establish known-good baseline

---

## Phase 2: Bug Fix 1 — Camera Release Race (US1)

**Purpose**: Fix `CountingService.stop()` to release the camera before joining the thread, so the next session can open immediately.

**⚠️ CRITICAL**: This is the most disruptive runtime bug — it leaves the camera locked after every stop.

### Test — US1 ⚠️ Written FIRST, confirmed FAIL before T003

- [x] T002 [US1] Write failing unit test: `stop()` calls `cap.release()` before `thread.join()` — in `tests/unit/test_counting_service.py`, mock `_cap` and `_thread`, capture call order via `side_effect`, assert `["cap_release", "thread_join"]`

### Implementation — US1

- [x] T003 [US1] Fix `CountingService.stop()` in `backend/services/counting_service.py` — set `_running=False`, call `_cap.release()` + `_cap=None`, then `_thread.join(timeout=5)`, then `_latest_frame=None`

**Checkpoint**: `pytest tests/unit/test_counting_service.py` passes for T002 test. Stop → immediate restart works without camera error.

---

## Phase 3: Bug Fix 2 — Windows Camera Handoff (US2)

**Purpose**: Prevent the black-screen / "Stream interrupted" error when navigating from calibration to counting on Windows.

### Implementation — US2 (no isolated unit tests; covered by manual verification and integration)

- [x] T004 [US2] Add 1 000 ms navigation delay in `frontend/js/calibrate.js` — after `stream.getTracks().forEach(t => t.stop())`, add `await new Promise(r => setTimeout(r, 1000))` before `location.href = ...`
- [x] T005 [US2] Add auto-retry state and `onStreamError()` handler in `frontend/js/count.js` — `autoRetries`, `MAX_AUTO_RETRIES=3`, `pageLoadTime`; silent retry up to 3 times within 15 s before showing error UI

**Checkpoint**: On Windows, completing calibration and navigating to the count page loads the stream automatically within 5 seconds.

---

## Phase 4: Bug Fix 3 — TOCTOU Camera Probe (US2)

**Purpose**: Remove the speculative `cv2.VideoCapture` pre-check in `stream.py` that creates a double-open race window.

### Implementation — US2 (internal implementation fix; no public API change)

- [x] T006 [US2] Remove TOCTOU pre-check block from `mjpeg_stream()` in `backend/routers/stream.py` — delete the `cv2.VideoCapture` probe and its surrounding try/finally; keep `import cv2` at top level (still used by `health()` and `list_cameras()`)

**Checkpoint**: `pytest` passes. Stream endpoint no longer opens the camera twice per request.

---

## Phase 5: Video Mode Removal (US3)

**Purpose**: Simplify calibration to photo-only, removing the mode-selection step and all video capture code.

### Implementation — US3

- [x] T007 [US3] Update `frontend/js/calibrate.js` — remove `captureMode` variable, `startVideoCapture()`, `sleep()`, `btn-video-mode` listener, `captureMode === "video"` branch; set `TOTAL_STEPS = 8`; update `btn-to-mode` to go directly to `startPhotoCapture()` + `showStep(3)`; hardcode `capture_mode: "photo"` in save body; shift all step references (quality→4, recapture→3, proposal→5, manual→6, accept→7, save-draw→7, door→8)
- [x] T008 [P] [US3] Update `frontend/calibrate.html` — delete Step 3 `<div>` (mode selection and countdown overlay); renumber step IDs (old 4→3 … old 9→8); change `btn-to-mode` text to "Next: Capture Photos →"; add `<div class="step-num-label">Step N of 8</div>` to each step header; change progress bar container class to `named-progress`

**Checkpoint**: Calibration wizard shows 8 steps; no mode-selection screen; photo capture begins immediately after Step 2.

---

## Phase 6: Backend Stats Enrichment (US4)

**Purpose**: Add `total_in`, `total_out`, and `session_count` to `GET /api/profiles` so the home page can display lifetime totals.

### Tests — US4 ⚠️ Written FIRST, confirmed FAIL before T011

- [x] T009 [P] [US4] Write failing integration test `test_list_profiles_has_stats_fields` in `tests/integration/test_profiles_api.py` — create a profile, call `GET /api/profiles`, assert response contains `total_in`, `total_out`, `session_count` keys
- [x] T010 [P] [US4] Write failing integration test `test_list_profiles_stats_zero_when_no_events` — assert all three stats fields are `0` for a profile with no sessions
- [x] T011 [P] [US4] Write failing integration test `test_list_profiles_stats_reflect_events` — insert events directly via DB helper, assert `total_in` and `total_out` match inserted event counts

### Implementation — US4

- [x] T012 [US4] Update `list_profiles()` in `backend/routers/profiles.py` — add a single SQL `LEFT JOIN events` aggregation query; merge stats dict into each profile object before returning

**Checkpoint**: `pytest tests/integration/test_profiles_api.py` passes for all three new tests. Home page shows correct totals.

---

## Phase 7: UI Redesign — CSS Tokens and Shared Styles (US4, US5, US6)

**Purpose**: Update design tokens and add new component CSS classes used by all three redesigned pages.

- [x] T013 [US4,US5,US6] Rewrite `frontend/css/styles.css` — update `--clr-bg`, `--clr-surface`, `--clr-border`; add `--radius-lg`, `--shadow-btn`; add `.app-header`, `.app-brand`, `.app-icon`, `.app-title`, `.app-sub`, `.profile-grid`, `.profile-card`, `.stats-row`, `.stat-cell`, `.count-header`, `.count-bar`, `.count-cell`, `.stream-badges`, `.stream-badge`, `.modal-backdrop`, `.modal`, `.banner`, `.live-dot`, `.events-log`, `.event-row`, `.fps-badge`, `.session-meta`, `.named-progress`, `.prog-step-wrap`, `.prog-connector`, `.prog-dot`, `.prog-inner-dot`, `.prog-label` component classes

---

## Phase 8: UI Redesign — Home Page (US4)

**Purpose**: Replace the plain profile list with data-rich cards showing lifetime stats.

- [x] T014 [US4] Rewrite `frontend/index.html` — app header with gradient icon + title + subtitle; Import button + "+ New Profile" primary button; profile grid rendered by `renderCard()`; stats row with `in-cell`/`out-cell` tinted cells; history modal; `escHtml()` XSS protection; `downloadCsv()` export handler

**Checkpoint**: Home page shows profile cards with IN/OUT lifetime stats. All existing functionality (History modal, Delete, Import, Export) works correctly.

---

## Phase 9: UI Redesign — Count Page (US5)

**Purpose**: Replace the flat count page layout with a polished stacked design including a session timer and tinted count cells.

- [x] T015 [US5] Rewrite `frontend/count.html` — header card with live-dot, profile name, session timer span, FPS badge, and Flip/Pause/Stop buttons; count bar with three tinted cells (in/out/occ) and `.count-sub` sub-labels; video wrapper with `.stream-badges` overlay; bottom panel grid with events card and actions card; stop modal preserved
- [x] T016 [US5] Update `frontend/js/count.js` — add `sessionStart`, `timerInterval`, `formatTimer(ms)` HH:MM:SS helper; set timer in `init()` from `session.started_at`; clear timer in stop handler; add `autoRetries`/`pageLoadTime`/`MAX_AUTO_RETRIES` stream auto-retry state; update all DOM element refs for new HTML IDs

**Checkpoint**: Count page shows session timer, tinted cells, and polished header. Stop modal works. Pause/Flip/Export/Grayscale buttons all function correctly.

---

## Phase 10: UI Redesign — Calibration Wizard Progress Bar (US6)

**Purpose**: Replace unlabelled dot progress with a named 8-step named progress bar.

- [x] T017 [US6] Update `frontend/js/calibrate.js` — replace old `renderDots()` with new named-step implementation: `STEP_NAMES = ["Camera","Preview","Capture","Quality","Boundary","Draw","Door","Save"]`; render `prog-step-wrap` + `prog-dot` + `prog-label` + `prog-connector` markup per step; checkmark for done, inner dot for current, empty for pending
- [x] T018 [P] [US6] Verify `frontend/calibrate.html` has `id="step-dots"` container and all 8 step divs with correct IDs (`step-1` … `step-8`) — confirm with the changes from T008

**Checkpoint**: Calibration wizard shows named progress bar; completed steps show "✓"; current step has purple glow; all 8 steps are reachable.

---

## Phase 11: Final Verification

- [x] T019 Run `pytest` — confirm 116/116 tests pass with zero regressions
- [x] T020 Manual smoke test: create profile → live count → stop → restart; verify no camera errors
- [x] T021 Manual smoke test: home page shows total_in/total_out after a session with events

---

## Dependencies & Execution Order

- Phase 1 (setup) must complete before any other phase
- Phases 2–4 (bug fixes) are independent of each other and can run in parallel
- Phase 5 (video removal) is independent; can run in parallel with bug fixes
- Phase 6 (backend stats) must complete before Phase 8 (home page redesign depends on the API response)
- Phase 7 (CSS) should complete before Phases 8–10 (HTML files reference new CSS classes)
- Phases 8–10 (UI redesign) are independent of each other after Phase 7
- Phase 11 (verification) runs last
