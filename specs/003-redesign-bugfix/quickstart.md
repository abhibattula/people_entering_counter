# Quickstart: UI Redesign, Bug Fixes & Video Mode Removal

**Phase**: 1 — Design & Contracts
**Date**: 2026-04-22

This document supplements `specs/001-doorway-people-counter/quickstart.md` with notes specific to this release. All setup and installation steps remain unchanged.

---

## What Changed

### Bug Fixes

**Stop & Restart No Longer Leaves Camera Busy**
- Clicking "Stop & Exit" now releases the camera before joining the background thread, so the next session starts cleanly without a "camera in use" error.

**Calibration → Count Page Loads Automatically on Windows**
- A 1-second delay after stopping camera tracks gives the OS time to release the handle before Python opens it.
- The count page silently retries the stream up to 3 times in the first 15 seconds before showing the manual "Retry" button.

**No More Double-Open Race on Stream Start**
- The speculative `cv2.VideoCapture` probe in `stream.py` has been removed, eliminating the TOCTOU race between the probe and the generator open.

### Video Mode Removed

- The calibration wizard no longer shows a mode-selection screen. It goes directly from "Frame Your Doorway" to the 5-photo guided capture.
- The wizard is now 8 steps (was 9). All step numbering is updated accordingly.
- Existing profiles with `capture_mode: "video"` continue to work — they load and start sessions normally.

### Home Page — Lifetime Stats on Profile Cards

- Each profile card now shows two tinted stat cells: **↑ Total In** (green) and **↓ Total Out** (red), aggregated from all sessions.
- The header has an app icon, title, subtitle, and a gradient "+ New Profile" button.
- Hovering a card lifts it with a purple top-stripe animation.

### Calibration Wizard — Named Step Progress Bar

- The old unlabelled dots are replaced by a named 8-step progress bar: **Camera → Preview → Capture → Quality → Boundary → Draw → Door → Save**.
- Completed steps show a filled purple dot with a "✓"; the current step has a purple glow ring; pending steps are grey.
- Connecting lines turn purple as steps complete.

### Count Page — Polished Layout

- A full-width header card shows: live dot, profile name, session timer (MM:SS / HH:MM:SS), FPS badge, and control buttons.
- The count bar cells are tinted — IN green, OUT red, Occupancy blue — each with a descriptive sub-label ("people entered", "people exited", "currently inside").
- The MJPEG stream area has rounded corners and a "● LIVE" overlay badge.
- The bottom panel has an Events log card and an Actions card side-by-side.

---

## Running Tests

```bash
# All tests (includes new counting_service and profiles API tests)
pytest

# Only the tests added in this release
pytest tests/unit/test_counting_service.py tests/integration/test_profiles_api.py -v

# With coverage
pytest --cov=backend tests/
```

---

## Verifying the Bug Fixes

**Stop & Restart race fix**:
1. Start a counting session.
2. Click "Stop & Exit" → confirm.
3. Immediately click "▶ Start Counting" on the same profile.
4. Expected: stream loads within 3 seconds, no error.

**Windows camera handoff fix**:
1. Complete a full calibration (camera permission → save profile).
2. Expected: count page loads automatically; stream appears within 5 seconds without clicking "Retry".

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Stream still fails after calibration | Wait the full 5 seconds; if it exceeds 3 retries, click "Retry" manually — the 1s delay may be insufficient on very slow machines |
| Profile card shows `0` totals | Only IN/OUT events from completed crossings count; no events recorded yet means totals are zero |
| Session timer starts at 00:00 and doesn't advance | Check that `started_at` is present in the session response; see browser console for errors |
| Old profile with video mode doesn't count | The `capture_mode` field is ignored at runtime — if a session fails it is a camera issue, not the capture_mode field |
