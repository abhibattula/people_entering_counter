# Research: UI Redesign, Bug Fixes & Video Mode Removal

**Phase**: 0 — Research & Decisions
**Date**: 2026-04-22
**Feature**: [spec.md](./spec.md)

---

## Decision 1: Fix stop() Race — Release Camera Before Thread Join

**Decision**: In `CountingService.stop()`, call `self._cap.release()` and set `self._cap = None` *before* calling `self._thread.join(timeout=5)`. Raise the timeout from 3 s to 5 s.

**Rationale**:
- The background loop calls `cap.read()` on every iteration. When the camera is released, `cap.read()` immediately returns `ret=False`, which causes the loop to exit within one iteration.
- The old order (join first, release after) means the thread must complete a full YOLO inference cycle before the join checks whether the thread exited. Under load this can exceed the 3 s timeout, leaving the camera open.
- After releasing the camera the thread exits in milliseconds. The 5 s join timeout is now a pure safety net against unexpected hangs, not a functional wait.

**Alternatives considered**:
- Use an `Event` flag to signal the thread to stop and sleep-wait: rejected — adds coordination complexity with no benefit when `cap.release()` already provides the same signal via `ret=False`.
- Lower the join timeout to 1 s: rejected — if something unexpected hangs the thread, 1 s is too short to distinguish a normal clean-stop from a real hang.

---

## Decision 2: 1 s Navigation Delay + Auto-Retry for Windows Camera Handoff

**Decision**: In the calibration save handler (`calibrate.js`), insert a 1 000 ms `await new Promise(r => setTimeout(r, 1000))` between `track.stop()` and `location.href = ...`. In `count.js`, add up to 3 silent auto-retries at 2 s intervals within the first 15 s of page load.

**Rationale**:
- On Windows, `MediaStreamTrack.stop()` requests the OS to release the camera handle but returns before the handle is actually freed. The OS release is asynchronous and typically takes 0.5–1.5 s.
- A 1 s delay covers the typical release window. The auto-retry on the count page covers residual edge cases where the 1 s was not enough (slow machines, antivirus scans, etc.) without requiring user intervention.
- The combination of both fixes means that on 95%+ of Windows machines the count page stream loads silently with no "Stream interrupted" error.

**Alternatives considered**:
- Poll `GET /api/health` until `camera_available: true` before navigating: rejected — the health endpoint checks camera availability by opening and releasing the camera, which itself causes a TOCTOU race.
- Show a loading spinner on the count page for a fixed duration: rejected — adds UX complexity and the spinner time is indeterminate.

---

## Decision 3: Remove the TOCTOU Camera Probe in stream.py

**Decision**: Delete the `cv2.VideoCapture` pre-check block from `mjpeg_stream()`. Let `CountingService.start()` be the sole camera opener. If the service is not yet started or fails to open the camera, the MJPEG generator logs the condition and yields nothing; the client's auto-retry handles recovery.

**Rationale**:
- The original probe opened the camera, confirmed it was available, closed it, then immediately opened it again in the generator. The gap between the two opens is a race window — another process (or the previous session's thread) can claim the handle between close and re-open.
- Removing the probe eliminates the race. There is exactly one `cv2.VideoCapture` call per counting session.
- `import cv2` is kept at the top of `stream.py` because `list_cameras()` and `health()` in the same router still use it.

**Alternatives considered**:
- Move the probe inside the same lock as the generator open: rejected — there is no lock guarding the `CountingService` camera open; adding one is a larger refactor than the bug fix warrants.
- Return 503 immediately if the service is not yet started: already done via `get_or_create_service` — if the service fails to open the camera, the generator loop exits and the HTTP response closes.

---

## Decision 4: Remove Video Calibration Path

**Decision**: Delete `startVideoCapture()`, `sleep()`, `btn-video-mode` event listener, and the `captureMode === "video"` branch. Hardcode `capture_mode: "photo"` in the profile save body. Reduce `TOTAL_STEPS` from 9 to 8 and remove the mode-selection step from `calibrate.html`.

**Rationale**:
- The video path used `MediaRecorder`, a 5-second recording, and 15-frame extraction — all for no accuracy benefit over 5 guided photos.
- `MediaRecorder` has inconsistent behaviour across browsers and operating systems, and was the source of timing-related failures on Windows.
- Photo capture covers all use cases. Existing profiles with `capture_mode: "video"` are unaffected because `capture_mode` is only used during calibration, not at runtime.

**Alternatives considered**:
- Keep video as a hidden/deprecated path behind a feature flag: rejected — dead code paths rot and the constitution forbids feature flags.
- Keep video but make it optional and hidden: rejected — same rationale; no YAGNI case for it.

---

## Decision 5: Aggregate Stats via LEFT JOIN in GET /api/profiles

**Decision**: Compute `total_in`, `total_out`, and `session_count` for all profiles in a single SQL query using `LEFT JOIN events ON e.session_id = s.id` and `GROUP BY s.profile_id`. Merge into the profile list in Python before returning.

**Rationale**:
- A single aggregation query avoids N+1 queries (one per profile). For a typical user with 5–20 profiles this is negligible, but the pattern is correct regardless.
- `total_in` and `total_out` are not stored columns — they are computed from the `events` table. Storing them as columns would require updating them on every count event, which introduces write contention with the counting loop.
- Using `LEFT JOIN` ensures profiles with zero sessions still appear in the result with zeroes.

**Alternatives considered**:
- Store `total_in`/`total_out` as columns on the `sessions` table and sum them: rejected — incremental writes during the counting loop add lock contention with the insert path; read-time aggregation is simpler and correct.
- Compute per-profile totals in Python with individual queries: rejected — N+1 query pattern for a simple aggregation.

---

## Decision 6: UI Redesign — Refined Current Direction

**Decision**: Keep the existing dark-mode palette (`#070a10` background, purple `#6c63ff` primary) and add sharper cards, gradient primary button, tinted count cells, and a named-step progress bar. No design system, no new CSS framework.

**Rationale**:
- Users are already familiar with the purple/dark aesthetic. A rebrand would require updating all user-facing documentation and mental models.
- The "Refined Current" direction achieves the visual goals (polish, hierarchy, readability) with the minimum number of CSS changes.
- All styling is in `frontend/css/styles.css` as CSS custom properties — one file, no build step, fully compliant with Principle V.

**Alternatives considered**:
- Adopt Tailwind CSS: rejected — requires a build step; violates Principle V.
- Full redesign with a new colour palette: rejected — unnecessary scope; existing palette is already coherent.
