# Feature Specification: UI Redesign, Bug Fixes & Video Mode Removal

**Feature Branch**: `003-redesign-bugfix`
**Created**: 2026-04-22
**Status**: Implemented
**Input**: Fix stop-session race condition, Windows camera-release hang, stream.py TOCTOU race; remove video calibration path; redesign all three pages (home, calibration wizard, count view) with a polished UI; expose lifetime totals on the profiles list endpoint.

---

## User Scenarios & Testing

### User Story 1 — Stop a Counting Session and Restart Without Camera Errors (Priority: P1)

A user clicks "Stop" during a counting session. The camera releases cleanly. They can immediately open the same profile again and start a new session — no "camera busy" error.

**Why this priority**: The camera release race causes the most damaging user-visible failure — the camera stays locked after stop and the next session's stream never loads. Every restart attempt ends in a broken stream until Python is restarted.

**Independent Test**: Stop a counting session and immediately click "Start Counting" again on the same profile. The stream loads within 3 seconds and counting resumes with no error.

**Acceptance Scenarios**:

1. **Given** a counting session is active, **When** the user confirms "Stop & Exit", **Then** the Python camera handle is released before the background thread is joined.
2. **Given** the camera has been released, **When** a new counting session is started for the same profile within 3 seconds, **Then** the MJPEG stream loads and bounding boxes appear without error.
3. **Given** the background thread is still finishing its last inference cycle, **When** the camera is released, **Then** `cap.read()` returns `ret=False` and the thread exits within one loop iteration.

---

### User Story 2 — Navigate from Calibration to Counting Without a Loading Hang (Priority: P1)

A user completes calibration and saves the profile. The page navigates to the live counting view and the stream loads within a few seconds — no black screen, no "Stream interrupted" error requiring a manual retry.

**Why this priority**: On Windows, the browser camera handle is not released synchronously. Every first-time calibration ends with a broken stream the user must manually retry. This is the second session-critical bug.

**Independent Test**: Complete a full calibration from camera permission through to profile save on Windows. The count page stream loads automatically within 5 seconds without the user clicking "Retry".

**Acceptance Scenarios**:

1. **Given** the profile save handler runs, **When** `stream.getTracks().forEach(t => t.stop())` is called, **Then** the page waits 1 000 ms before navigating to `count.html`.
2. **Given** the count page loads, **When** the MJPEG stream request fails within the first 15 seconds, **Then** the browser silently retries up to 3 times at 2-second intervals before showing the manual "Retry" button.
3. **Given** the stream.py router receives a stream request, **When** the counting service is not yet open, **Then** no speculative `cv2.VideoCapture` probe is opened (eliminating the double-open race).

---

### User Story 3 — Complete Calibration Using Only Photos (Priority: P2)

A user sets up a new door profile using the 5-photo guided capture. The calibration wizard has no video option — it goes directly from "Frame Your Doorway" to the capture step. The flow is 8 steps, not 9.

**Why this priority**: The video calibration path added complexity (MediaRecorder, countdown, 5-second clip) with no accuracy benefit over photos. Removing it simplifies the wizard and eliminates a source of platform compatibility issues.

**Independent Test**: A user completes calibration from camera permission to live counting using only photos — with no mode-selection screen in between.

**Acceptance Scenarios**:

1. **Given** the calibration wizard is open at Step 2 (Preview), **When** the user clicks "Next: Capture Photos →", **Then** the wizard advances directly to the photo capture step (Step 3) with no mode-selection screen.
2. **Given** the profile is saved, **When** the profile JSON is written to disk, **Then** `capture_mode` is always `"photo"` for new profiles.
3. **Given** an existing profile has `capture_mode: "video"`, **When** that profile is loaded for a new session, **Then** no error is thrown and the session starts normally.

---

### User Story 4 — See Lifetime Usage Stats on the Home Page (Priority: P2)

A user opens the app and immediately sees how many people have entered and exited each doorway across all sessions — without opening a history modal. The data is visible on each profile card.

**Why this priority**: Lifetime totals are the primary reason a user revisits the home page. Without them, the cards are decorative; with them, the page is a useful dashboard.

**Independent Test**: Create a profile, run a session, generate 3 IN and 2 OUT events. Return to the home page. The profile card shows "↑ Total In: 3" and "↓ Total Out: 2" without opening History.

**Acceptance Scenarios**:

1. **Given** a profile has had one or more completed sessions with events, **When** the home page loads, **Then** each profile card displays the lifetime total IN count and lifetime total OUT count aggregated from all sessions.
2. **Given** a profile has never had any events, **When** the home page loads, **Then** the profile card shows zero for both totals.
3. **Given** `GET /api/profiles` is called, **When** the response is received, **Then** each profile object contains `total_in`, `total_out`, and `session_count` integer fields.

---

### User Story 5 — Monitor a Live Counting Session With Rich Context (Priority: P2)

A user on the count page can see the profile name, a running session timer, live IN/OUT/Occupancy counts in coloured cells, and control buttons — all without scrolling. The layout is polished and immediately readable.

**Why this priority**: The count page is the primary working screen. A poor layout causes confusion about which number is which, and the absence of a session timer makes it impossible to know how long the session has been running.

**Independent Test**: Open a counting session. Within 3 seconds a non-technical observer can identify: which profile is active, how long the session has been running, the current IN count (green), OUT count (red), and Occupancy count (blue).

**Acceptance Scenarios**:

1. **Given** a counting session is active, **When** the count page loads, **Then** a header card displays: live-dot animation, profile name, running session timer (MM:SS format), and Flip/Pause/Stop buttons.
2. **Given** a counting session has been running for 75 minutes, **When** the timer renders, **Then** it displays `01:15:00` (HH:MM:SS format).
3. **Given** counting events occur, **When** the count bar renders, **Then** the IN cell is tinted green, the OUT cell is tinted red, and the Occupancy cell is tinted blue — each with a descriptive sub-label.

---

### User Story 6 — Follow Calibration Progress With Named Steps (Priority: P3)

A user going through calibration can see exactly where they are in an 8-step named progress bar (Camera → Preview → Capture → Quality → Boundary → Draw → Door → Save). Completed steps show a purple checkmark; the current step pulses.

**Why this priority**: The old unlabelled dots gave no indication of what each step was. Named steps reduce anxiety and let users plan how long setup will take.

**Independent Test**: A user completing calibration for the first time can name the next step before clicking through to it, based only on the progress bar.

**Acceptance Scenarios**:

1. **Given** the calibration wizard is at Step 4 (Quality), **When** the progress bar renders, **Then** steps 1–3 show a purple filled dot with a "✓", step 4 shows a pulsing border with a purple inner dot, and steps 5–8 show empty grey dots.
2. **Given** a step is completed, **When** the progress bar updates, **Then** its dot fills purple with a "✓" and the connecting line to the next step turns purple.
3. **Given** a step label is rendered, **When** it corresponds to the current step, **Then** the label is white and bold; when it corresponds to a completed step, it is purple; when pending, it is muted grey.

---

### Edge Cases

- What if `started_at` is missing from the session response? → The session timer shows `00:00` and does not start.
- What if the events table has no rows for a profile? → `total_in` and `total_out` are both `0`.
- What if the stream auto-retry limit (3 retries / 15 s) is reached? → The manual "Retry" button appears and auto-retries stop.
- What if a profile has `capture_mode: "video"` in its JSON? → The profile loads and counts normally; the `capture_mode` field is ignored at runtime.
- What if the user presses Stop, then immediately navigates back before the thread finishes? → The thread joins with a 5-second timeout; any subsequent session open will succeed after the timeout.

---

## Requirements

### Functional Requirements

- **FR-001**: `CountingService.stop()` MUST release the camera (`_cap.release()`) before joining the background thread (`_thread.join()`).
- **FR-002**: The calibration save handler MUST wait 1 000 ms after `stream.getTracks().forEach(t => t.stop())` before navigating to `count.html`.
- **FR-003**: The count page stream error handler MUST silently retry the stream up to 3 times at 2-second intervals if the failure occurs within 15 seconds of page load.
- **FR-004**: `mjpeg_stream()` in `stream.py` MUST NOT open a speculative `cv2.VideoCapture` to probe camera availability before the MJPEG generator runs.
- **FR-005**: The calibration wizard MUST have exactly 8 steps; Step 3 (mode selection) is removed; `btn-to-mode` navigates directly to photo capture.
- **FR-006**: New profiles MUST always be saved with `capture_mode: "photo"`.
- **FR-007**: Existing profiles with `capture_mode: "video"` MUST load and start sessions without error.
- **FR-008**: `GET /api/profiles` MUST return `total_in`, `total_out`, and `session_count` for each profile, computed from the `events` and `sessions` tables.
- **FR-009**: The count page MUST display a session timer that updates every second in MM:SS format (switching to HH:MM:SS after 60 minutes), starting from `session.started_at`.
- **FR-010**: The count page count bar MUST display three tinted cells (IN: green, OUT: red, Occupancy: blue) each with a numeric value and a descriptive sub-label.
- **FR-011**: The calibration wizard progress bar MUST show 8 named steps with connecting lines; completed steps show a filled purple dot with "✓", the current step shows a purple-bordered dot with a glow ring and inner dot, pending steps show an empty grey-bordered dot.
- **FR-012**: The home page profile cards MUST display `total_in` and `total_out` in two tinted stat cells (IN: green, OUT: red).

### Key Entities

- **Door Profile** (`backend/profiles/{uuid}.json`): Unchanged schema. `capture_mode` field retained for backward compatibility; new profiles always write `"photo"`. Runtime: `session_count`, `total_in`, `total_out` are added transiently to the API response.
- **Session** (`sessions` table): `started_at` is returned in `POST /api/sessions/start` response so the count page can start the timer from the correct reference point.
- **Event** (`events` table): Used for aggregate totals in `GET /api/profiles` via `LEFT JOIN` + conditional `COUNT`.

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: After clicking "Stop & Exit" and immediately clicking "Start Counting" on the same profile, the stream loads within 3 seconds with zero camera errors on both Windows and macOS.
- **SC-002**: After completing calibration on Windows, the count page stream loads automatically within 5 seconds on 95% of first-time navigations.
- **SC-003**: The calibration wizard completes end-to-end (camera permission → profile saved) using only the photo path, with no mode-selection screen visible.
- **SC-004**: All 116 existing automated tests pass after implementation with zero regressions.
- **SC-005**: A profile card on the home page displays correct `total_in` / `total_out` values after any completed session adds events.
- **SC-006**: The count page session timer starts from `session.started_at` and stays in sync (±1 second) with wall-clock time for sessions up to 24 hours.

---

## Assumptions

- The `started_at` field already exists in the `POST /api/sessions/start` response; no schema migration is needed.
- `total_in`, `total_out`, and `session_count` are computed on every `GET /api/profiles` request from the live database; they are not cached or stored as columns.
- Existing profiles (including those with `capture_mode: "video"`) are fully backward-compatible — no migration script is needed.
- The 1 000 ms navigation delay in `calibrate.js` is sufficient for the Windows camera handle release in all common scenarios; the 3-retry auto-retry on the count page handles the remaining edge cases.
- Frontend remains vanilla JS + CSS; no new Python or npm dependencies are introduced.
