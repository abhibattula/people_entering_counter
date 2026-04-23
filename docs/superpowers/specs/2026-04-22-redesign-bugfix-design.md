# Design: UI Redesign + Bug Fixes + Video Removal

**Date**: 2026-04-22  
**Spec**: `specs/003-redesign-bugfix/spec.md`  
**Approach**: Single integrated spec — bug fixes, video removal, and full UI redesign in one pass

---

## Summary

Fix three confirmed runtime bugs, remove the video calibration path, and redesign all three pages (home, calibration wizard, count view) with a polished, user-friendly UI. The visual direction is **Refined Current** — same purple/violet brand, sharper cards, better spacing, subtle gradients, coloured count cells, and a named-step progress bar in the wizard.

---

## Section 1 — Bug Fixes

### Bug 1: Stop / Camera-Release Race Condition

**Root cause**: `CountingService.stop()` joins the background thread (3 s timeout) *before* releasing the camera. If YOLO inference takes longer than 3 s, the join times out and the thread keeps running with the camera open. If the user immediately starts a new session, a second `CountingService` is created and its `cv2.VideoCapture` fails because the first thread still holds the handle.

**Fix**: Swap the order in `stop()` — release the camera *first*, then join the thread. Releasing the camera causes `cap.read()` to return `ret=False` immediately, so the thread exits within one loop iteration rather than waiting for a full YOLO inference cycle. Raise join timeout to 5 s as a safety net.

```python
def stop(self) -> None:
    self._running = False
    if self._cap:           # release FIRST — unblocks the thread
        self._cap.release()
        self._cap = None
    if self._thread:        # join AFTER
        self._thread.join(timeout=5)
    self._latest_frame = None
```

**File**: `backend/services/counting_service.py`

---

### Bug 2: Calibration → Count Page Loading Hang (Windows Camera Release Timing)

**Root cause**: On Windows, `MediaStreamTrack.stop()` in the browser does not synchronously release the OS camera handle. Python's `cv2.VideoCapture` call (triggered by navigating to count.html) can fail immediately after calibration because the OS handle is still held by the browser for 0.5–1.5 s.

**Fix — two parts**:

1. `calibrate.js` (step 9 save handler): add a 1 000 ms pause between stopping camera tracks and navigating. This gives the OS time to release the handle before Python tries to open it.

```js
if (stream) stream.getTracks().forEach(t => t.stop());
await new Promise(r => setTimeout(r, 1000));   // ← new
location.href = `/count.html?profile_id=${id}`;
```

2. `count.js` (stream error handler): add auto-retry on first-load stream failure. If `streamImg.onerror` fires within 15 s of page load, automatically retry up to 3 times at 2 s intervals before showing the manual "Retry" button. This silently recovers from transient camera-release lag without user intervention.

```js
let autoRetries = 0;
const MAX_AUTO_RETRIES = 3;
const pageLoadTime = Date.now();

function onStreamError() {
  const elapsed = Date.now() - pageLoadTime;
  if (autoRetries < MAX_AUTO_RETRIES && elapsed < 15000) {
    autoRetries++;
    setTimeout(startStream, 2000);
  } else {
    streamError.classList.remove("hidden");
  }
}
```

**Files**: `frontend/js/calibrate.js`, `frontend/js/count.js`

---

### Bug 3: `stream.py` Camera Double-Open (TOCTOU Race)

**Root cause**: `mjpeg_stream` opens the camera with `cv2.VideoCapture` to check availability, releases it, then the MJPEG generator opens it again. On Windows the brief release between the two opens can be claimed by another process (or the previous session's thread).

**Fix**: Remove the pre-check `cv2.VideoCapture` probe entirely. Let `CountingService.start()` be the sole camera opener. If it fails with `RuntimeError`, the generator logs it and returns; the frontend's auto-retry (Bug 2 fix) handles recovery.

**File**: `backend/routers/stream.py`

---

## Section 2 — Video Mode Removal

The video calibration path (`MediaRecorder`, 5-second clip, 15-frame extraction) is removed. Photo-only calibration is simpler and covers all use cases.

### Backend

- `ProfileCreate.capture_mode` field kept as-is (existing profiles with `"video"` still load without error); new profiles always save `"photo"`.

### Frontend — `calibrate.html`

- Remove Step 3 (mode selection) — the two `📷` / `📹` buttons and their wrapper `<div>`.
- Step 2 "Frame Your Doorway" button text changes to **"Next: Capture Photos →"** and navigates directly to the capture step.
- Steps renumber: old 4 → 3, old 5 → 4, … old 9 → 8. `TOTAL_STEPS = 8`.

### Frontend — `calibrate.js`

- Remove `captureMode` variable; hardcode `capture_mode: "photo"` in the save body.
- Remove `startVideoCapture()` function (~45 lines).
- Remove `btn-video-mode` event listener.
- Remove `captureMode === "video"` branch in `btn-recapture` listener.
- Remove `sleep()` utility if no longer used.
- Update `TOTAL_STEPS = 8`.
- Shift all step references down by 1 after old Step 3 removal.

---

## Section 3 — UI Redesign

### Design Tokens (CSS variables — `frontend/css/styles.css`)

Existing tokens are preserved. New additions:

```css
--clr-bg:       #070a10;    /* slightly deeper than current #0f1117 */
--clr-surface:  #111520;    /* cards */
--clr-border:   #1e2540;    /* subtler than current #2e3148 */
--radius-lg:    12px;       /* cards */
--radius:        8px;       /* buttons, inputs */
--shadow-card:  0 4px 24px rgba(0,0,0,.5);
--shadow-btn:   0 2px 8px rgba(108,99,255,.3);
```

---

### Home Page (`frontend/index.html` + inline script)

**App header** (replaces plain `<header>`):
- Left: 40 × 40 px gradient icon (`linear-gradient(135deg,#6c63ff,#a78bfa)`) + app title + subtitle.
- Right: Import button + "**+ New Profile**" primary button.
- Separator: `border-bottom: 1px solid var(--clr-border)`.

**Profile cards** (replaces `.profile-card`):
- Border-radius 12 px, `background: var(--clr-surface)`.
- Top purple gradient strip (`::before`, 3 px, visible on hover) + `translateY(-2px)` hover lift.
- Status dot: green pulsing (active session) or dim (idle).
- Session count + created date as card meta.
- **Stats row**: two tinted cells — IN (`rgba(34,197,94,.08)` bg, green border) and OUT (`rgba(248,113,113,.08)` bg, red border), showing lifetime totals.
- Actions row: **▶ Start Counting** (full-width gradient primary), **History** (ghost), **✕** delete (ghost, red on hover).

**Backend change** (`backend/routers/profiles.py`): `GET /api/profiles` enriched to include `total_in` and `total_out` lifetime totals per profile. Totals are computed from the `events` table (they are not stored columns in `sessions`):

```python
row = conn.execute(
    "SELECT COUNT(CASE WHEN e.direction='in'  THEN 1 END) AS total_in, "
    "       COUNT(CASE WHEN e.direction='out' THEN 1 END) AS total_out "
    "FROM events e "
    "JOIN sessions s ON e.session_id = s.id "
    "WHERE s.profile_id = ?", (p["id"],)
).fetchone()
p["total_in"]  = row["total_in"]
p["total_out"] = row["total_out"]
```

**Active session indicator**: the status dot is green-pulsing when `GET /api/sessions?profile_id=X` returns at least one row with `ended_at IS NULL`; otherwise dim grey. Fetched client-side at load time alongside the profile list.

---

### Calibration Wizard (`frontend/calibrate.html` + `calibrate.js`)

**Named progress bar** (replaces `.step-progress` dots):

8 named steps connected by lines: **Camera → Preview → Capture → Quality → Boundary → Direction → Door → Save**.

Each step node:
- 20 × 20 px circle, `border: 2px solid var(--clr-border)`.
- **Done**: filled purple (`#6c63ff`), white `✓` inside.
- **Current**: empty with purple glow ring (`box-shadow: 0 0 0 3px rgba(108,99,255,.25)`) and inner purple dot.
- **Pending**: dim border, grey.
- Connecting lines: 2 px, grey (pending) → purple (done).
- Labels below each dot: small, muted when pending, white+bold when current, purple when done.

**Step cards** styled with `border-radius: 12px`, step label ("Step N of 8") in purple above the heading.

**Active step highlight**: `border: 1px solid rgba(108,99,255,.5)` + subtle glow shadow.

**Quality badges**: rounded 8 px, tinted borders (green/warning/error).

**Buttons**: all rounded 8 px, primary gets gradient + box-shadow.

---

### Count Page (`frontend/count.html` + `count.js`)

**Header card** (new `<div class="count-header">`):
- Left: live dot + profile name + session timer + FPS badge (`background: rgba(108,99,255,.15)`).
- Right: Flip Direction, Pause, Stop buttons.
- `background: var(--clr-surface)`, `border-radius: 12px`, full-width.

**Session timer**: `count.js` tracks `sessionStart = Date.now()` on init, updates a `<span id="session-timer">` every second via `setInterval`. Format: `MM:SS` (switches to `HH:MM:SS` once ≥ 1 hour).

**Count bar** (`.count-bar`):
- Tinted cells: IN green, OUT red, OCC blue — each with coloured bg + border.
- Sub-label below number: "people entered", "people exited", "currently inside".
- `border-radius: 12px` per cell.

**Stream area**: `border-radius: 12px`, overlay badges ("● LIVE", "N fps") top-right inside the stream wrapper.

**Bottom panel**: events card (left) + actions card (right), both `border-radius: 12px`.

**Events log rows**: `border-radius: 6px` per row.

---

## Files Changed

| File | Change |
|---|---|
| `backend/services/counting_service.py` | Bug 1: swap camera release order in `stop()` |
| `backend/routers/stream.py` | Bug 3: remove TOCTOU camera pre-check |
| `backend/routers/profiles.py` | Add `total_in`/`total_out` to list endpoint |
| `frontend/js/calibrate.js` | Bug 2a: 1 s delay; video removal; named progress bar wiring |
| `frontend/js/count.js` | Bug 2b: auto-retry; session timer; new DOM refs |
| `frontend/calibrate.html` | Remove Step 3; named progress bar HTML; 8-step renumber |
| `frontend/count.html` | Header card; tinted count cells; stream badges; bottom panel |
| `frontend/index.html` | App header; data-rich profile cards; stats display |
| `frontend/css/styles.css` | Updated tokens; new component classes |

---

## Constraints

- No new npm dependencies, no build step — vanilla JS + CSS only.
- No new Python dependencies.
- Backend remains `fastapi`, `uvicorn`, `ultralytics`, `opencv-python`, `aiofiles`.
- Existing profiles (including those with `capture_mode: "video"`) load without modification.
- All existing API contracts preserved; `GET /api/profiles` response gains two optional fields (`total_in`, `total_out`).
- TDD mandatory per constitution: tests written before implementation for all backend changes.
