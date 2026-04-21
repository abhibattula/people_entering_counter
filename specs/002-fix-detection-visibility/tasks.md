# Tasks: Detection Accuracy & Visual Clarity Fixes

**Input**: Design documents from `specs/002-fix-detection-visibility/`
**Prerequisites**: plan.md ✅ · spec.md ✅ · research.md ✅ · data-model.md ✅ · contracts/api.md ✅

**TDD Note**: Per the project constitution (Principle III), tests MUST be written and confirmed to FAIL before any implementation task begins. Each test task below must be completed before the implementation tasks it precedes.

**Format**: `[ID] [P?] [Story?] Description with file path`
- **[P]**: Parallelisable (touches different files, no cross-task dependency)
- **[Story]**: User Story that this task serves

---

## Phase 1: Setup

**Purpose**: Confirm the existing test suite is green before any changes are made. This establishes a known-good baseline so regressions are immediately detectable.

- [X] T001 Run `pytest` and confirm all existing tests pass; fix any pre-existing failures before proceeding

---

## Phase 2: Foundational — FPS Guard (blocks all counting tests)

**Purpose**: The FPS divide-by-zero in `counting_service.get_fps` silently kills the background thread, making every subsequent counting test unreliable. Fix this first.

**⚠️ CRITICAL**: No US1–US7 counting work can be validated until this thread-crash risk is eliminated.

- [X] T002 Write failing unit test for zero-duration FPS window in `tests/unit/test_counting_service.py` — assert `get_fps()` returns `0.0` when all frame timestamps are identical, assert no exception is raised
- [X] T003 Fix FPS guard in `backend/services/counting_service.py` — in `get_fps()`, return `0.0` when `d[-1] == d[0]`; also correct the formula from `len(d)` to `len(d)-1` intervals
- [X] T004 Write failing unit test that CountingService background thread logs an error and stops cleanly (rather than crashing silently) when `_loop` raises an unhandled exception — in `tests/unit/test_counting_service.py`
- [X] T005 Wrap `counting_service._loop` body in `try/except Exception` with `logger.exception(...)` in `backend/services/counting_service.py` so thread failures surface in `logs/app.log`

**Checkpoint**: `pytest tests/unit/test_counting_service.py` passes for T002 and T004 tests.

---

## Phase 3: User Story 1 — People Detected and Shown Immediately (Priority: P1) 🎯 MVP

**Goal**: Fix the camera resolution mismatch (Bug 1) and the ByteTrack ID gate (Bug 2) so that green bounding boxes appear on every person inside the ROI from the first frame, regardless of motion.

**Independent Test**: Open an existing profile, stand still in front of the camera. A green bounding box appears within 1 second and stays while standing still.

### Tests — US1 ⚠️ Write FIRST, confirm FAIL before T008/T009

- [X] T006 [P] [US1] Write failing unit test: `CountingService.start()` must call `cap.set(CAP_PROP_FRAME_WIDTH, profile['frame_width'])` and `cap.set(CAP_PROP_FRAME_HEIGHT, ...)` in `tests/unit/test_counting_service.py` — mock `cv2.VideoCapture` and assert the set calls occur with the profile values
- [X] T007 [P] [US1] Write failing unit test: when `r.boxes.id is None` for a frame where YOLO detects a person inside the ROI, `cv2.rectangle` is still called on the annotated frame — in `tests/unit/test_counting_service.py`

### Implementation — US1

- [X] T008 [US1] Fix camera resolution in `backend/services/counting_service.py` — in `CountingService.start()`, after `cv2.VideoCapture(camera_index)` succeeds, call `cap.set(cv2.CAP_PROP_FRAME_WIDTH, profile['frame_width'])` and `cap.set(cv2.CAP_PROP_FRAME_HEIGHT, profile['frame_height'])`; log a warning if the returned resolution does not match
- [X] T009 [US1] Split detection drawing from tracking gate in `backend/services/counting_service.py` — refactor `_loop` to two passes: (1) detection pass draws bounding boxes for all class-0 YOLO detections inside ROI (dim green `(0, 180, 0)` when no track ID, full green `(0, 255, 0)` when tracked); (2) tracking pass checks line crossings only for detections with an assigned track ID and a known previous centroid

**Checkpoint**: `pytest tests/unit/test_counting_service.py` passes. Live stream shows bounding boxes on a stationary person.

---

## Phase 4: User Story 2 — Door Boundary Accurately Proposed and Clearly Shown (Priority: P1)

**Goal**: Fix YOLO heatmap missing from calibration (Bug 3), arbitrary polygon corner selection (Bug 4), and the overly permissive door visibility check (Bug 8). Add a DOOR label overlay to the live stream.

**Independent Test**: Calibrate with someone walking through the doorway. The proposed polygon encloses the door frame. The live stream shows "DOOR" next to the boundary.

### Tests — US2 ⚠️ Write FIRST, confirm FAIL before T013–T015

- [X] T010 [P] [US2] Write failing unit test: `propose_doorway()` with synthetic frames containing YOLO person detections in the left half of the frame proposes an ROI polygon that overlaps the left half — in `tests/unit/test_calibration_service.py`
- [X] T011 [P] [US2] Write failing unit test: `_detect_roi` on a contour with 6 approximated points returns a 4-point polygon ordered TL→TR→BR→BL — in `tests/unit/test_calibration_service.py`
- [X] T012 [P] [US2] Write failing unit test: `_check_door_visibility` returns `False` for a solid-colour frame with many edge pixels but no contour reaching 2+ frame edges — in `tests/unit/test_quality_service.py`

### Implementation — US2

- [X] T013 [US2] Implement YOLO person-density corridor in `backend/services/calibration_service.py` — add `_build_person_mask(frames, model)` that runs `model(frame, verbose=False)` on each frame, accumulates person (class 0) bounding box regions into a binary mask, and blurs the result; update `_detect_roi` to score each candidate contour by `area_ratio * (1 + overlap_ratio_with_mask)` and select the highest scorer; fall back to existing Canny-only approach when no person detections exist
- [X] T014 [US2] Fix polygon corner extraction in `backend/services/calibration_service.py` — replace `pts = approx.reshape(-1, 2).tolist(); pts = _order_quad(pts[:4])` with `rect = cv2.minAreaRect(best_contour); box = cv2.boxPoints(rect).astype(int).tolist(); pts = _order_quad(box)`
- [X] T015 [P] [US2] Tighten door visibility check in `backend/services/quality_service.py` — add `_contour_touches_n_edges(contours, frame, n=2)` helper that checks if any contour bounding box touches ≥2 frame edges; update `_check_door_visibility` to require both `has_edges AND touches_edges`
- [X] T016 [P] [US2] Add "DOOR" text label overlay in `backend/services/counting_service.py` — in `_draw_overlays`, after drawing the ROI polygon, add `cv2.putText` with text `"DOOR"` at position `(min_x_of_roi, max(min_y_of_roi - 8, 15))` in purple `(128, 0, 128)`, `FONT_HERSHEY_SIMPLEX`, scale 0.7, thickness 2

**Checkpoint**: `pytest tests/unit/test_calibration_service.py tests/unit/test_quality_service.py` passes. Calibration wizard proposes a door-shaped polygon.

---

## Phase 5: User Story 3 — Inside/Outside Direction Is Correct (Priority: P1)

**Goal**: Give users a "Flip direction" button in step 6 of the calibration wizard so the saved `inside_direction` always reflects their explicit choice.

**Independent Test**: Calibrate, see the direction arrow pointing the wrong way, click "Flip direction", click "Yes, this looks right". Walk through the door in the "inside" direction — the IN counter increments.

### Implementation — US3

*(Pure front-end change; no backend logic altered.)*

- [X] T017 [US3] Add "Flip direction" button to `frontend/calibrate.html` step 6 — insert `<button class="btn btn-ghost" id="btn-flip-direction">↔ Flip direction</button>` between the reject and accept buttons in the proposal step
- [X] T018 [US3] Implement flip direction logic in `frontend/js/calibrate.js` — add a module-level `let flippedDirection = null`; in `showProposalStep()`, reset `flippedDirection = null`; add event listener for `btn-flip-direction` that toggles `inside_direction` between `up`↔`down` and `left`↔`right` in a local copy, redraws the direction arrow on the proposal canvas, and updates `proposalResult.inside_direction` so it is saved correctly

**Checkpoint**: In the calibration wizard, the direction arrow flips on button click. The saved profile has the user-confirmed direction.

---

## Phase 6: User Story 4 — Manual Draw Works with Clear Visual Feedback (Priority: P2)

**Goal**: Fix the canvas redraw bug, replace tiny dots with numbered markers, and add a click progress counter.

**Independent Test**: A user clicks 4 corners in manual draw mode. Numbered circles (1–4) appear at each click with the background image still visible. A label shows "Tap corner N of 4" updating with each click.

### Implementation — US4

*(Pure front-end; no backend tests required.)*

- [X] T019 [US4] Fix background redraw in `frontend/js/calibrate.js` — add `let drawBgImage = null`; assign `drawBgImage = img` inside `startManualDraw`'s `img.onload` callback; update `redrawManual(canvas)` to begin with `ctx.clearRect(0, 0, canvas.width, canvas.height)` then `ctx.drawImage(drawBgImage, 0, 0)` before drawing any markers (guard with `if (drawBgImage)`)
- [X] T020 [US4] Replace 5px dot markers with numbered circles in `frontend/js/calibrate.js` — update the `drawPoints.forEach` branch of `redrawManual` to draw: filled white circle (radius 14px), purple fill circle (radius 12px), white centred text showing corner number ("1"–"4") at font-size 14px bold
- [X] T021 [US4] Add progress label to `frontend/calibrate.html` step 7 — insert `<p id="draw-progress" style="color:var(--clr-muted);font-size:.9rem">Tap corner 1 of 4</p>` above the canvas wrapper div
- [X] T022 [US4] Wire progress label to click count in `frontend/js/calibrate.js` — after each `drawPoints.push(...)`, update `document.getElementById("draw-progress").textContent` to "Tap corner N of 4" (N = drawPoints.length + 1) or "All corners placed — click Save →" after the 4th click; also reset label to "Tap corner 1 of 4" in `startManualDraw`

**Checkpoint**: Manual draw mode shows numbered markers and progress text. Clicking Reset restores the background image cleanly.

---

## Phase 7: User Story 5 — Counting Line Clearly Visible (Priority: P2)

**Goal**: Make the counting line thicker (3px) and add a "COUNT LINE" text label so it is immediately recognisable on any background.

**Independent Test**: Open the live counting view. The counting line is visible and labelled without any explanation needed.

### Implementation — US5

- [X] T023 [US5] Increase counting line thickness and add label in `backend/services/counting_service.py` — in `_draw_overlays`, change the `cv2.line` call thickness from 2 to 3; add `cv2.putText` with text `"COUNT LINE"`, position `(mx - 50, line['y1'] - 8)`, `FONT_HERSHEY_SIMPLEX`, scale 0.5, yellow `(0, 255, 255)`, thickness 1

**Checkpoint**: Live stream clearly shows the counting line with label.

---

## Phase 8: User Story 7 — System Remains Stable (Priority: P2)

**Goal**: The remaining stability fix — tighten the door visibility quality check so it does not pass on blank walls (Bug 8 already implemented as T015 above). Verify thread stability holds under irregular frame rates.

*(Note: T015 covers the door visibility fix. T002–T005 cover the FPS and thread-crash fixes. This phase adds a final verification.)*

- [X] T024 [US7] Run `pytest tests/unit/test_counting_service.py tests/unit/test_quality_service.py` and confirm all stability-related tests pass; investigate any failures before proceeding

**Checkpoint**: All stability tests pass.

---

## Phase 9: User Story 6 — Grayscale Mode (Priority: P3)

**Goal**: Add a per-session grayscale toggle that reduces per-frame memory usage and maintains ≥10 fps on low-spec machines.

**Independent Test**: Toggle grayscale in the live view. Stream switches to B&W within 2 seconds. People boxes and overlays remain visible. FPS stays ≥10.

### Tests — US6 ⚠️ Write FIRST, confirm FAIL before T026–T031

- [X] T025 [P] [US6] Write failing integration test: `GET /stream?profile_id=...&grayscale=true` returns MJPEG frames where R==G==B per pixel (greyscale) — in `tests/integration/test_stream_grayscale.py`; use the existing async `client` fixture and a mock profile

### Implementation — US6

- [X] T026 [US6] Add `_grayscale` flag and `set_grayscale(enabled: bool)` method to `CountingService` in `backend/services/counting_service.py`; default `_grayscale = False`
- [X] T027 [US6] Apply grayscale conversion in `backend/services/counting_service.py` — at end of `_loop`, after `_draw_overlays` but before `cv2.imencode`, add: `if self._grayscale: annotated = cv2.cvtColor(cv2.cvtColor(annotated, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)`
- [X] T028 [US6] Add `grayscale` query param to `/stream` route in `backend/routers/stream.py` — accept `grayscale: bool = False`; after getting/creating the service, call `svc.set_grayscale(grayscale)`
- [X] T029 [P] [US6] Add grayscale toggle button to `frontend/count.html` — insert `<button class="btn btn-ghost" id="btn-grayscale">🔲 Grayscale</button>` inside the bottom actions card
- [X] T030 [US6] Implement grayscale toggle in `frontend/js/count.js` — add event listener for `btn-grayscale`; maintain a `let grayscaleOn = false` boolean; on click toggle it and reload `streamImg.src` with `&grayscale=true` or without the param; update button text to "🔲 Grayscale" / "🎨 Colour"

**Checkpoint**: `pytest tests/integration/test_stream_grayscale.py` passes. Toggle works in browser; FPS remains ≥10.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [X] T031 [P] Run full `pytest` suite with coverage — `pytest --cov=backend tests/` — and confirm no regressions; record coverage report
- [ ] T032 Manual smoke test per `specs/002-fix-detection-visibility/quickstart.md` — walk through calibration, reject and flip direction, use manual draw, verify live stream shows DOOR label and COUNT LINE label, toggle grayscale, check CSV export still works

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS Phases 3–9 (FPS crash must be fixed before counting tests run)
- **Phase 3 (US1)**: Depends on Phase 2
- **Phase 4 (US2)**: Depends on Phase 2 — independent of Phase 3 (different service files)
- **Phase 5 (US3)**: Depends on Phase 2 — independent of Phases 3–4 (front-end only)
- **Phase 6 (US4)**: Depends on Phase 5 (flip direction must be wired before manual draw save is confirmed)
- **Phase 7 (US5)**: Depends on Phase 3 (changes same file: `counting_service._draw_overlays`)
- **Phase 8 (US7)**: Depends on Phases 2–4 (verifies all stability fixes are in place)
- **Phase 9 (US6)**: Depends on Phase 3 (adds to `CountingService`) and Phase 7 (confirmed stream works)
- **Phase 10 (Polish)**: Depends on all previous phases

### Parallel Opportunities Within Phases

After Phase 2 completes, these task groups can run in parallel:
- **Group A**: T006–T009 (US1, counting_service)
- **Group B**: T010–T016 (US2, calibration_service + quality_service)
- **Group C**: T017–T018 (US3, calibrate.html + calibrate.js)

Within Phase 4: T010, T011, T012 can all be written in parallel (different test cases). T015 and T016 can run in parallel (different files).

---

## Implementation Strategy

### MVP (Phases 1–3 only — P1 people detection fixed)

1. Phase 1: Baseline green
2. Phase 2: FPS guard in place
3. Phase 3: Resolution fix + detection drawing split
4. **STOP and VALIDATE**: Stand still in front of camera — boxes appear immediately

### Full Fix Delivery (Phases 1–8)

Phases 3–5 can be parallelised by two developers after Phase 2. Phase 4 is the largest chunk (4 test tasks, 4 impl tasks).

### Complete Release (all 10 phases)

Total: **32 tasks** across 10 phases.

---

## Notes

- Constitution Principle III (TDD) is mandatory: every test task must reach a FAILING state before the paired implementation task runs
- `[P]` tasks operate on different files; they can be opened in separate editor tabs and run simultaneously
- Each phase ends with a checkpoint — stop to verify before moving to the next phase
- The grayscale feature (Phase 9) is lowest priority; it can be deferred without blocking any other fix
