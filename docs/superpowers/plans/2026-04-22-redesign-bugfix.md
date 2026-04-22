# UI Redesign + Bug Fixes + Video Removal — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three camera-session bugs, remove the video calibration path, and redesign all three pages (home, wizard, count view) with a polished purple/violet UI.

**Architecture:** Backend bug fixes first (counting_service, stream, profiles), then frontend JS fixes, then pure HTML/CSS/JS redesign in page order. TDD for all backend changes; frontend tasks are direct implementation.

**Tech Stack:** Python 3.10+ / FastAPI / SQLite (backend) · Vanilla JS / HTML / CSS (frontend) · pytest + httpx (tests)

---

## File Map

| File | What changes |
|---|---|
| `backend/services/counting_service.py` | `stop()` — release camera before joining thread |
| `backend/routers/stream.py` | Remove TOCTOU camera pre-check |
| `backend/routers/profiles.py` | `list_profiles()` — add `total_in`, `total_out`, `session_count` |
| `frontend/js/calibrate.js` | 1 s nav delay · remove video mode · named progress bar |
| `frontend/js/count.js` | Auto-retry stream · session timer · new DOM refs |
| `frontend/calibrate.html` | Remove step 3 · named progress bar · renumber steps |
| `frontend/count.html` | Header card · tinted count cells · stream badges · bottom panel |
| `frontend/index.html` | App header · data-rich profile cards · lifetime stats |
| `frontend/css/styles.css` | Updated tokens · new component classes |
| `tests/unit/test_counting_service.py` | Test for stop() order fix |
| `tests/integration/test_profiles_api.py` | Tests for stats in list endpoint |

---

## Task 1: Fix CountingService.stop() — release camera before joining thread

**Files:**
- Modify: `backend/services/counting_service.py` (~lines 130–138)
- Test: `tests/unit/test_counting_service.py`

**Background:** Currently `stop()` calls `self._thread.join(timeout=3)` first, then releases the camera. If YOLO inference takes > 3 s, the join times out and the thread keeps running with the camera open. When the user starts a new session, `cv2.VideoCapture` fails because the first thread still holds the handle.

**Fix:** Release the camera *before* joining the thread. This causes `cap.read()` to return `ret=False` immediately so the thread exits within milliseconds.

- [ ] **Step 1.1 — Write failing test**

Add to `tests/unit/test_counting_service.py`:

```python
# ── Stop order (Task 1 fix) ───────────────────────────────────────────────

def test_stop_releases_camera_before_joining_thread():
    """Camera must be released BEFORE the thread is joined so the thread can detect
    the release via cap.read() → ret=False and exit without waiting for YOLO."""
    import threading
    from backend.services.counting_service import CountingService

    svc = CountingService()
    mock_cap = MagicMock()
    mock_thread = MagicMock(spec=threading.Thread)

    svc._cap = mock_cap
    svc._thread = mock_thread
    svc._running = True

    call_order = []
    mock_cap.release.side_effect = lambda: call_order.append("cap_release")
    mock_thread.join.side_effect = lambda timeout=None: call_order.append("thread_join")

    svc.stop()

    assert call_order == ["cap_release", "thread_join"], (
        f"Expected camera release BEFORE thread join, got: {call_order}"
    )
    assert svc._cap is None
    assert not svc._running
    assert svc._latest_frame is None
```

- [ ] **Step 1.2 — Run test, confirm FAIL**

```
pytest tests/unit/test_counting_service.py::test_stop_releases_camera_before_joining_thread -v
```

Expected: `FAILED — assert ['thread_join', 'cap_release'] == ['cap_release', 'thread_join']`

- [ ] **Step 1.3 — Implement fix**

In `backend/services/counting_service.py`, replace the `stop()` method (currently ~lines 130–138):

```python
def stop(self) -> None:
    self._running = False
    if self._cap:           # release FIRST — unblocks the loop via ret=False
        self._cap.release()
        self._cap = None
    if self._thread:        # join AFTER — thread exits quickly once cap is gone
        self._thread.join(timeout=5)
    self._latest_frame = None
```

- [ ] **Step 1.4 — Run test, confirm PASS**

```
pytest tests/unit/test_counting_service.py::test_stop_releases_camera_before_joining_thread -v
```

Expected: `PASSED`

- [ ] **Step 1.5 — Run full unit suite, confirm no regressions**

```
pytest tests/unit/test_counting_service.py -v
```

Expected: all tests pass.

- [ ] **Step 1.6 — Commit**

```bash
git add backend/services/counting_service.py tests/unit/test_counting_service.py
git commit -m "fix: release camera before joining thread in CountingService.stop()"
```

---

## Task 2: Remove TOCTOU camera pre-check in stream.py

**Files:**
- Modify: `backend/routers/stream.py`

**Background:** `mjpeg_stream` opens the camera with `cv2.VideoCapture`, checks if it opened, releases it, then the MJPEG generator opens it again. On Windows, the brief release between the two opens can be claimed by the previous session's thread, causing a false "camera unavailable" 503 or a race with the new session.

**Fix:** Remove the entire pre-check block. `CountingService.start()` is the sole camera opener. If it fails, the generator catches the `RuntimeError`; the frontend auto-retry (Task 3) handles recovery.

- [ ] **Step 2.1 — Edit stream.py**

In `backend/routers/stream.py`, replace the `mjpeg_stream` function with:

```python
@router.get("/stream")
async def mjpeg_stream(profile_id: str, grayscale: bool = False):
    svc = get_or_create_service(profile_id)
    svc.set_grayscale(grayscale)
    return StreamingResponse(
        _mjpeg_generator(profile_id, grayscale=grayscale),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
```

Also remove the `import cv2` line at the top of stream.py if `cv2` is no longer used anywhere else in that file. Check: `cv2` is only used in the removed pre-check block. Remove `import cv2` from stream.py.

The `_mjpeg_generator` already handles the `RuntimeError` from `svc.start()` via the `try/except` block in `_loop` — if the camera can't open, the loop exits cleanly and the generator stops yielding frames; the frontend sees a broken MJPEG stream and triggers auto-retry.

- [ ] **Step 2.2 — Run integration tests, confirm no regressions**

```
pytest tests/integration/ -v
```

Expected: all existing tests pass.

- [ ] **Step 2.3 — Commit**

```bash
git add backend/routers/stream.py
git commit -m "fix: remove TOCTOU camera double-open probe in stream.py"
```

---

## Task 3: Frontend bug fixes — nav delay + stream auto-retry

**Files:**
- Modify: `frontend/js/calibrate.js`
- Modify: `frontend/js/count.js`

**No backend changes — no new tests required.**

### Part A: calibrate.js — 1 s delay before navigation

In `calibrate.js`, find the `btn-save` click listener (near the bottom, in the `// ── Step 9: Save` section). Replace the navigation line:

- [ ] **Step 3.1 — Add delay in calibrate.js**

Find this block (currently the last few lines of the `btn-save` listener):

```javascript
  try {
    const { id } = await createProfile(body);
    // Release browser camera before Python/OpenCV takes over (constitution Principle IV)
    if (stream) stream.getTracks().forEach(t => t.stop());
    location.href = `/count.html?profile_id=${id}`;
  } catch (e) {
```

Replace with:

```javascript
  try {
    const { id } = await createProfile(body);
    // Release browser camera before Python/OpenCV takes over (constitution Principle IV)
    if (stream) stream.getTracks().forEach(t => t.stop());
    // Wait 1 s for the OS to fully release the camera handle (Windows timing)
    await new Promise(r => setTimeout(r, 1000));
    location.href = `/count.html?profile_id=${id}`;
  } catch (e) {
```

### Part B: count.js — auto-retry on first-load stream failure

- [ ] **Step 3.2 — Add auto-retry state to count.js**

Near the top of `count.js`, after the existing `let` declarations (after `let wsRetries = 0;`), add:

```javascript
let autoRetries = 0;
const MAX_AUTO_RETRIES = 3;
const pageLoadTime = Date.now();
```

- [ ] **Step 3.3 — Update onStreamError in count.js**

Find the `onStreamError` function:

```javascript
function onStreamError() {
  streamError.classList.remove("hidden");
}
```

Replace with:

```javascript
function onStreamError() {
  const elapsed = Date.now() - pageLoadTime;
  if (autoRetries < MAX_AUTO_RETRIES && elapsed < 15000) {
    autoRetries++;
    setTimeout(startStream, 2000);   // silent retry — camera may still be releasing
  } else {
    streamError.classList.remove("hidden");
  }
}
```

- [ ] **Step 3.4 — Commit**

```bash
git add frontend/js/calibrate.js frontend/js/count.js
git commit -m "fix: add 1s camera release delay and stream auto-retry after calibration"
```

---

## Task 4: Add lifetime stats to GET /api/profiles

**Files:**
- Modify: `backend/routers/profiles.py`
- Test: `tests/integration/test_profiles_api.py`

**Background:** The home page profile cards need to display lifetime IN/OUT totals and session count. These must be added to the `GET /api/profiles` response. Totals are computed by joining the `events` and `sessions` tables — `total_in`/`total_out` are NOT stored columns in `sessions`, they're derived from the `events` table.

- [ ] **Step 4.1 — Write failing tests**

Add to `tests/integration/test_profiles_api.py`:

```python
@pytest.mark.asyncio
async def test_list_profiles_has_stats_fields(api_client):
    """GET /api/profiles must include total_in, total_out, session_count fields."""
    await api_client.post("/api/profiles", json=VALID_PROFILE)
    resp = await api_client.get("/api/profiles")
    assert resp.status_code == 200
    profiles = resp.json()
    assert len(profiles) > 0
    p = profiles[0]
    assert "total_in"      in p, "total_in missing from profile list"
    assert "total_out"     in p, "total_out missing from profile list"
    assert "session_count" in p, "session_count missing from profile list"
    assert isinstance(p["total_in"],      int)
    assert isinstance(p["total_out"],     int)
    assert isinstance(p["session_count"], int)


@pytest.mark.asyncio
async def test_list_profiles_stats_zero_when_no_events(api_client):
    """A freshly created profile with no sessions has all stats at 0."""
    resp = await api_client.post("/api/profiles", json={**VALID_PROFILE, "name": "Stats Zero Test"})
    profile_id = resp.json()["id"]
    list_resp = await api_client.get("/api/profiles")
    p = next((x for x in list_resp.json() if x["id"] == profile_id), None)
    assert p is not None
    assert p["total_in"]      == 0
    assert p["total_out"]     == 0
    assert p["session_count"] == 0


@pytest.mark.asyncio
async def test_list_profiles_stats_reflect_events(api_client):
    """total_in and total_out reflect actual events inserted for that profile."""
    from backend.db.database import get_connection, insert_event

    resp = await api_client.post("/api/profiles", json={**VALID_PROFILE, "name": "Stats Events Test"})
    profile_id = resp.json()["id"]

    # Create a session via API
    sess_resp = await api_client.post("/api/sessions/start", json={"profile_id": profile_id})
    assert sess_resp.status_code in (200, 201)
    session_id = sess_resp.json()["session_id"]

    # Insert 2 IN + 1 OUT events directly into the DB
    conn = get_connection()
    try:
        insert_event(conn, session_id, profile_id, "in",  1)
        insert_event(conn, session_id, profile_id, "in",  2)
        insert_event(conn, session_id, profile_id, "out", 1)
    finally:
        conn.close()

    list_resp = await api_client.get("/api/profiles")
    p = next((x for x in list_resp.json() if x["id"] == profile_id), None)
    assert p is not None
    assert p["total_in"]  == 2
    assert p["total_out"] == 1
```

- [ ] **Step 4.2 — Run tests, confirm FAIL**

```
pytest tests/integration/test_profiles_api.py::test_list_profiles_has_stats_fields tests/integration/test_profiles_api.py::test_list_profiles_stats_zero_when_no_events tests/integration/test_profiles_api.py::test_list_profiles_stats_reflect_events -v
```

Expected: all three FAIL with `KeyError` or `AssertionError` (fields not present).

- [ ] **Step 4.3 — Implement**

In `backend/routers/profiles.py`, replace the `list_profiles` function:

```python
@router.get("/profiles")
def list_profiles():
    from backend.db.database import get_connection
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    profiles = []
    for f in PROFILES_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            profiles.append({
                "id":         data["id"],
                "name":       data["name"],
                "created_at": data["created_at"],
            })
        except Exception:
            pass
    profiles.sort(key=lambda p: p["created_at"], reverse=True)

    if not profiles:
        return profiles

    # Enrich with lifetime event counts and session count (one DB query for all profiles)
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT s.profile_id, "
            "  COUNT(DISTINCT s.id)                         AS session_count, "
            "  COUNT(CASE WHEN e.direction='in'  THEN 1 END) AS total_in, "
            "  COUNT(CASE WHEN e.direction='out' THEN 1 END) AS total_out "
            "FROM sessions s "
            "LEFT JOIN events e ON e.session_id = s.id "
            "GROUP BY s.profile_id"
        ).fetchall()
        stats = {r["profile_id"]: dict(r) for r in rows}
    finally:
        conn.close()

    for p in profiles:
        s = stats.get(p["id"], {"session_count": 0, "total_in": 0, "total_out": 0})
        p["session_count"] = s["session_count"]
        p["total_in"]      = s["total_in"]
        p["total_out"]     = s["total_out"]

    return profiles
```

- [ ] **Step 4.4 — Run tests, confirm PASS**

```
pytest tests/integration/test_profiles_api.py -v
```

Expected: all tests pass (new + existing).

- [ ] **Step 4.5 — Commit**

```bash
git add backend/routers/profiles.py tests/integration/test_profiles_api.py
git commit -m "feat: add total_in, total_out, session_count to GET /api/profiles"
```

---

## Task 5: Remove video capture mode

**Files:**
- Modify: `frontend/calibrate.html`
- Modify: `frontend/js/calibrate.js`

**No backend tests — frontend only.**

### Part A: calibrate.html

- [ ] **Step 5.1 — Remove Step 3 (mode selection) from calibrate.html**

Remove the entire Step 3 block:

```html
  <!-- Step 3: Mode selection -->
  <div class="step" id="step-3">
    <div class="step-header"><h2>Choose Capture Mode</h2></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
      <button class="btn btn-ghost" id="btn-photo-mode" style="padding:1.5rem;flex-direction:column;height:auto">
        <span style="font-size:2rem">📷</span>
        <strong>5-Photo Guided</strong>
        <small style="color:var(--clr-muted)">More accurate</small>
      </button>
      <button class="btn btn-ghost" id="btn-video-mode" style="padding:1.5rem;flex-direction:column;height:auto">
        <span style="font-size:2rem">📹</span>
        <strong>5-Second Video</strong>
        <small style="color:var(--clr-muted)">Quicker</small>
      </button>
    </div>
  </div>
```

- [ ] **Step 5.2 — Renumber step divs in calibrate.html**

Rename the remaining step `id` attributes: old step-4 → step-3, old step-5 → step-4, …, old step-9 → step-8. Also update the Step 2 next button:

Change:
```html
<button class="btn btn-primary" id="btn-to-mode">Next: Choose Capture Mode →</button>
```
To:
```html
<button class="btn btn-primary" id="btn-to-mode">Next: Capture Photos →</button>
```

- [ ] **Step 5.3 — Remove countdown overlay and video elements no longer needed**

The `#countdown-overlay` div inside step-3 (now step-3/capture step) is only used by video mode. Remove it:

```html
<div id="countdown-overlay" class="countdown-overlay hidden"></div>
```

Also remove the `#thumb-strip` div? No — keep it, it's used by photo mode thumbnails.

- [ ] **Step 5.4 — Replace step-dots div with named progress container**

Replace:
```html
<div class="step-progress" id="step-dots"></div>
```
With:
```html
<div class="named-progress" id="step-dots"></div>
```

### Part B: calibrate.js

- [ ] **Step 5.5 — Update TOTAL_STEPS and step references**

Replace `const TOTAL_STEPS = 9;` with `const TOTAL_STEPS = 8;`.

Remove the `let captureMode = "photo";` declaration.

- [ ] **Step 5.6 — Remove video mode code**

Remove the `startVideoCapture` function (the entire function, ~45 lines starting at `async function startVideoCapture()`).

Remove the `sleep` utility function:
```javascript
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
```

Remove the `btn-video-mode` listener:
```javascript
document.getElementById("btn-video-mode").addEventListener("click", () => {
  captureMode = "video";
  startVideoCapture(); showStep(4);
});
```

Remove the `btn-photo-mode` listener:
```javascript
document.getElementById("btn-photo-mode").addEventListener("click", () => {
  captureMode = "photo"; photoIndex = 0;
  startPhotoCapture(); showStep(4);
});
```

- [ ] **Step 5.7 — Update btn-to-mode to go directly to photo capture**

Replace:
```javascript
document.getElementById("btn-to-mode").addEventListener("click", () => showStep(3));
```
With:
```javascript
document.getElementById("btn-to-mode").addEventListener("click", () => {
  photoIndex = 0;
  startPhotoCapture();
  showStep(3);
});
```

- [ ] **Step 5.8 — Fix all showStep() calls (old numbers → new numbers)**

| Old call | New call | Location |
|---|---|---|
| `showStep(5)` in `showQualityStep()` | `showStep(4)` | inside `showQualityStep` |
| `showStep(4)` in `btn-recapture` | `showStep(3)` | recapture listener |
| `showStep(6)` in `showProposalStep()` | `showStep(5)` | inside `showProposalStep` |
| `showStep(7)` in `startManualDraw()` | `showStep(6)` | inside `startManualDraw` |
| `showStep(8)` in `btn-accept-proposal` | `showStep(7)` | accept listener |
| `showStep(8)` in `btn-save-draw` | `showStep(7)` | save draw listener |
| `showStep(9)` in `btn-door-no` | `showStep(8)` | door no listener |
| `showStep(9)` in `btn-door-yes` | `showStep(8)` | door yes listener |

Also in `btn-recapture`, remove the `if (captureMode === "video")` branch — just:
```javascript
document.getElementById("btn-recapture").addEventListener("click", () => {
  photoIndex = 0; capturedFrames = [];
  startPhotoCapture(); showStep(3);
});
```

- [ ] **Step 5.9 — Hardcode capture_mode in save body**

In the `btn-save` listener, replace `capture_mode: captureMode,` with `capture_mode: "photo",`.

- [ ] **Step 5.10 — Update renderDots to named progress bar**

Replace the `renderDots()` function with:

```javascript
const STEP_NAMES = ["Camera", "Preview", "Capture", "Quality", "Boundary", "Draw", "Door", "Save"];

function renderDots() {
  dots.innerHTML = STEP_NAMES.map((name, i) => {
    const n = i + 1;
    const cls = n < currentStep ? "done" : n === currentStep ? "current" : "";
    const inner = n < currentStep
      ? `<span style="font-size:.55rem;color:#fff">✓</span>`
      : n === currentStep
        ? `<span class="prog-inner-dot"></span>`
        : "";
    const connector = i < TOTAL_STEPS - 1
      ? `<div class="prog-connector${n < currentStep ? " done" : ""}"></div>`
      : "";
    return `
      <div class="prog-step-wrap">
        <div class="prog-dot ${cls}">${inner}</div>
        <div class="prog-label ${cls}">${name}</div>
      </div>
      ${connector}`;
  }).join("");
}
```

- [ ] **Step 5.11 — Commit**

```bash
git add frontend/calibrate.html frontend/js/calibrate.js
git commit -m "feat: remove video calibration mode, rename steps 1-8, named progress bar"
```

---

## Task 6: CSS — update design tokens and add new component classes

**Files:**
- Modify: `frontend/css/styles.css`

- [ ] **Step 6.1 — Update design tokens in :root**

Replace the entire `:root` block:

```css
:root {
  --clr-bg:        #070a10;
  --clr-surface:   #111520;
  --clr-border:    #1e2540;
  --clr-primary:   #6c63ff;
  --clr-success:   #22c55e;
  --clr-warning:   #f59e0b;
  --clr-error:     #ef4444;
  --clr-text:      #e2e8f0;
  --clr-muted:     #64748b;
  --clr-in:        #22c55e;
  --clr-out:       #f87171;
  --clr-occupancy: #60a5fa;

  --radius:    8px;
  --radius-lg: 12px;
  --gap:       1rem;
  --shadow:    0 4px 24px rgba(0,0,0,.5);
  --shadow-btn: 0 2px 8px rgba(108,99,255,.3);
}
```

- [ ] **Step 6.2 — Update btn-primary to gradient**

Replace:
```css
.btn-primary  { background: var(--clr-primary); color: #fff; }
```
With:
```css
.btn-primary  { background: linear-gradient(135deg, #6c63ff, #8b80ff); color: #fff; box-shadow: var(--shadow-btn); }
```

- [ ] **Step 6.3 — Update .card border-radius**

Replace:
```css
.card {
  background: var(--clr-surface);
  border: 1px solid var(--clr-border);
  border-radius: var(--radius);
  padding: 1.5rem;
  box-shadow: var(--shadow);
}
```
With:
```css
.card {
  background: var(--clr-surface);
  border: 1px solid var(--clr-border);
  border-radius: var(--radius-lg);
  padding: 1.5rem;
  box-shadow: var(--shadow);
}
```

- [ ] **Step 6.4 — Update .profile-card for hover lift and top strip**

Replace the existing `.profile-card` block with:

```css
.profile-card {
  padding: 1.25rem;
  border-radius: var(--radius-lg);
  border: 1px solid var(--clr-border);
  background: var(--clr-surface);
  display: flex;
  flex-direction: column;
  gap: .75rem;
  position: relative;
  overflow: hidden;
  transition: border-color .2s, transform .15s, box-shadow .2s;
}
.profile-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, #6c63ff, #a78bfa);
  opacity: 0;
  transition: opacity .2s;
}
.profile-card:hover { border-color: #3d3d6b; transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,.4); }
.profile-card:hover::before { opacity: 1; }
.profile-card h3      { font-size: 1.05rem; }
.profile-card .meta   { font-size: .8rem; color: var(--clr-muted); }
.profile-card .actions { display: flex; gap: .5rem; margin-top: auto; }
```

- [ ] **Step 6.5 — Add profile stats cells**

Append after the `.profile-card` section:

```css
/* ── Profile stats row (home page cards) ───────────────────────────── */
.stats-row { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; }
.stat-cell {
  border-radius: var(--radius);
  padding: .6rem .75rem;
  display: flex; flex-direction: column; gap: .1rem;
}
.stat-cell.in-cell  { background: rgba(34,197,94,.08);  border: 1px solid rgba(34,197,94,.18); }
.stat-cell.out-cell { background: rgba(248,113,113,.08); border: 1px solid rgba(248,113,113,.18); }
.stat-label { font-size: .65rem; font-weight: 600; text-transform: uppercase; letter-spacing: .07em; color: var(--clr-muted); }
.stat-value { font-size: 1.35rem; font-weight: 800; line-height: 1.1; }
.stat-cell.in-cell  .stat-value { color: var(--clr-in); }
.stat-cell.out-cell .stat-value { color: var(--clr-out); }
```

- [ ] **Step 6.6 — Add app-header styles (home page)**

```css
/* ── App header (home page) ─────────────────────────────────────────── */
.app-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 2rem; padding-bottom: 1.25rem;
  border-bottom: 1px solid var(--clr-border);
}
.app-brand { display: flex; align-items: center; gap: .75rem; }
.app-icon {
  width: 40px; height: 40px; border-radius: 10px;
  background: linear-gradient(135deg, #6c63ff, #a78bfa);
  display: flex; align-items: center; justify-content: center; font-size: 1.3rem;
  box-shadow: 0 4px 14px rgba(108,99,255,.4);
  flex-shrink: 0;
}
.app-title { font-size: 1.2rem; font-weight: 700; letter-spacing: -.01em; }
.app-sub   { font-size: .8rem; color: var(--clr-muted); margin-top: .1rem; }
```

- [ ] **Step 6.7 — Add count-header styles (count page)**

```css
/* ── Count page header card ─────────────────────────────────────────── */
.count-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 1rem; padding: .75rem 1rem;
  background: var(--clr-surface); border: 1px solid var(--clr-border);
  border-radius: var(--radius-lg);
}
.count-header .header-left  { display: flex; align-items: center; gap: .75rem; }
.count-header .header-right { display: flex; gap: .5rem; }
.profile-title { font-size: 1.05rem; font-weight: 700; }
.session-meta  { font-size: .75rem; color: var(--clr-muted); display: flex; align-items: center; gap: .6rem; margin-top: .1rem; }
.fps-badge {
  background: rgba(108,99,255,.15); border: 1px solid rgba(108,99,255,.25);
  color: #a78bfa; padding: .1rem .45rem; border-radius: 4px;
  font-size: .7rem; font-weight: 600;
}
```

- [ ] **Step 6.8 — Update count-bar cells to tinted**

Replace the `.count-cell` block:

```css
.count-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 1.1rem 1rem;
  background: var(--clr-surface);
  border-radius: var(--radius-lg);
  border: 1px solid;
}
.count-cell .count-label { font-size: .7rem; font-weight: 700; color: var(--clr-muted); text-transform: uppercase; letter-spacing: .07em; }
.count-cell .count-value { font-size: 3rem; font-weight: 900; line-height: 1.1; }
.count-cell .count-sub   { font-size: .7rem; color: var(--clr-muted); }
.count-cell.in  { background: rgba(34,197,94,.07);  border-color: rgba(34,197,94,.2); }
.count-cell.out { background: rgba(248,113,113,.07); border-color: rgba(248,113,113,.2); }
.count-cell.occ { background: rgba(96,165,250,.07);  border-color: rgba(96,165,250,.2); }
.count-cell.in  .count-value { color: var(--clr-in); }
.count-cell.out .count-value { color: var(--clr-out); }
.count-cell.occ .count-value { color: var(--clr-occupancy); }
```

Also update `.count-bar` (remove `background: var(--clr-border)` which created the 1px dividers):

```css
.count-bar {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: .75rem;
  margin-bottom: .75rem;
}
```

- [ ] **Step 6.9 — Add stream overlay badge style**

```css
/* ── Stream overlay badges ──────────────────────────────────────────── */
.stream-badges {
  position: absolute; top: .6rem; right: .6rem;
  display: flex; gap: .4rem; z-index: 2;
}
.stream-badge {
  background: rgba(0,0,0,.65); border: 1px solid rgba(255,255,255,.1);
  border-radius: 6px; padding: .25rem .6rem;
  font-size: .7rem; color: var(--clr-text);
}
```

- [ ] **Step 6.10 — Add named progress bar styles (calibration wizard)**

```css
/* ── Named step progress bar (calibration wizard) ───────────────────── */
.named-progress {
  display: flex; align-items: flex-start; margin-bottom: 1.5rem;
}
.prog-step-wrap { display: flex; flex-direction: column; align-items: center; gap: .3rem; flex-shrink: 0; }
.prog-connector { flex: 1; height: 2px; background: var(--clr-border); margin: 0 2px; margin-bottom: 1.4rem; min-width: 8px; }
.prog-connector.done { background: var(--clr-primary); }
.prog-dot {
  width: 20px; height: 20px; border-radius: 50%;
  border: 2px solid var(--clr-border);
  background: var(--clr-bg);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; transition: all .2s;
}
.prog-dot.done    { background: var(--clr-primary); border-color: var(--clr-primary); }
.prog-dot.current { border-color: var(--clr-primary); box-shadow: 0 0 0 3px rgba(108,99,255,.25); }
.prog-inner-dot   { width: 8px; height: 8px; border-radius: 50%; background: var(--clr-primary); }
.prog-label { font-size: .6rem; color: var(--clr-muted); text-align: center; line-height: 1.2; white-space: nowrap; }
.prog-label.done    { color: var(--clr-primary); }
.prog-label.current { color: var(--clr-text); font-weight: 600; }

/* Step label inside active step card */
.step-num-label { font-size: .65rem; font-weight: 700; text-transform: uppercase; letter-spacing: .07em; color: var(--clr-primary); margin-bottom: .15rem; }
```

- [ ] **Step 6.11 — Add status dot for profile cards**

```css
/* ── Profile status dot (home page) ────────────────────────────────── */
.status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.status-dot.active { background: var(--clr-success); box-shadow: 0 0 6px rgba(34,197,94,.5); animation: pulse 1.4s ease-in-out infinite; }
.status-dot.idle   { background: var(--clr-border); }
```

- [ ] **Step 6.12 — Commit**

```bash
git add frontend/css/styles.css
git commit -m "style: update design tokens, add tinted count cells, profile cards, progress bar CSS"
```

---

## Task 7: Redesign home page (index.html)

**Files:**
- Modify: `frontend/index.html`

- [ ] **Step 7.1 — Replace index.html with redesigned version**

Replace the entire content of `frontend/index.html` with:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Doorway Counter</title>
  <link rel="stylesheet" href="/css/styles.css">
</head>
<body>
<div class="container">

  <header class="app-header">
    <div class="app-brand">
      <div class="app-icon">🚪</div>
      <div>
        <div class="app-title">Doorway Counter</div>
        <div class="app-sub">Track who enters and exits your space</div>
      </div>
    </div>
    <div style="display:flex;gap:.6rem;align-items:center">
      <label class="btn btn-ghost" style="cursor:pointer">
        ⬆ Import
        <input type="file" id="import-input" accept=".json" style="display:none">
      </label>
      <a href="/calibrate.html" class="btn btn-primary">+ New Profile</a>
    </div>
  </header>

  <div id="import-banner" class="banner banner-info hidden" style="margin-bottom:1rem"></div>

  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
    <h2 style="font-size:.9rem;font-weight:600;color:var(--clr-muted);text-transform:uppercase;letter-spacing:.06em">Saved Profiles</h2>
    <span id="profile-count" style="font-size:.8rem;color:var(--clr-muted)"></span>
  </div>

  <div id="profiles-list">
    <div class="card" style="text-align:center;padding:3rem">
      <p style="color:var(--clr-muted);margin-bottom:1rem">No door profiles yet</p>
      <a href="/calibrate.html" class="btn btn-primary">Create Your First Profile</a>
    </div>
  </div>

  <!-- Session history modal -->
  <div id="history-modal" class="hidden" style="position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:100;display:flex;align-items:center;justify-content:center">
    <div class="card" style="width:min(700px,95vw);max-height:80vh;overflow-y:auto">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
        <h3 id="history-title">Session History</h3>
        <button class="btn btn-ghost" id="close-history">✕</button>
      </div>
      <div id="history-list"></div>
    </div>
  </div>
</div>

<script type="module">
import { getProfiles, deleteProfile, importProfile, getSessions, exportSession } from "/js/api.js";

const list          = document.getElementById("profiles-list");
const profileCount  = document.getElementById("profile-count");
const historyModal  = document.getElementById("history-modal");
const historyTitle  = document.getElementById("history-title");
const historyList   = document.getElementById("history-list");
const importInput   = document.getElementById("import-input");
const importBanner  = document.getElementById("import-banner");

async function loadProfiles() {
  const profiles = await getProfiles().catch(() => []);
  if (profiles.length === 0) {
    profileCount.textContent = "";
    return;
  }
  profileCount.textContent = `${profiles.length} profile${profiles.length !== 1 ? "s" : ""}`;
  list.innerHTML = `<div class="profile-grid">${profiles.map(renderCard).join("")}</div>`;
  list.querySelectorAll("[data-start]").forEach(btn =>
    btn.addEventListener("click", () => location.href = `/count.html?profile_id=${btn.dataset.start}`)
  );
  list.querySelectorAll("[data-history]").forEach(btn =>
    btn.addEventListener("click", () => showHistory(btn.dataset.history, btn.dataset.name))
  );
  list.querySelectorAll("[data-delete]").forEach(btn =>
    btn.addEventListener("click", () => confirmDelete(btn.dataset.delete))
  );
}

function renderCard(p) {
  const created = new Date(p.created_at).toLocaleDateString();
  const sessions = p.session_count || 0;
  const meta = `Created ${created} · ${sessions} session${sessions !== 1 ? "s" : ""}`;
  return `
    <div class="profile-card">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div>
          <h3>${escHtml(p.name)}</h3>
          <p class="meta" style="margin-top:.2rem">${meta}</p>
        </div>
      </div>
      <div class="stats-row">
        <div class="stat-cell in-cell">
          <span class="stat-label">↑ Total In</span>
          <span class="stat-value">${p.total_in ?? 0}</span>
        </div>
        <div class="stat-cell out-cell">
          <span class="stat-label">↓ Total Out</span>
          <span class="stat-value">${p.total_out ?? 0}</span>
        </div>
      </div>
      <div class="actions">
        <button class="btn btn-primary" style="flex:1;justify-content:center" data-start="${p.id}">▶ Start Counting</button>
        <button class="btn btn-ghost" data-history="${p.id}" data-name="${escHtml(p.name)}">History</button>
        <button class="btn btn-danger" data-delete="${p.id}" title="Delete profile">✕</button>
      </div>
    </div>`;
}

async function confirmDelete(id) {
  if (!confirm("Delete this profile and all its sessions?")) return;
  await deleteProfile(id).catch(e => alert(e.message));
  loadProfiles();
}

async function showHistory(profileId, name) {
  historyTitle.textContent = `${name} — Session History`;
  historyList.innerHTML = `<p style="color:var(--clr-muted)">Loading…</p>`;
  historyModal.classList.remove("hidden");
  const sessions = await getSessions(profileId).catch(() => []);
  if (sessions.length === 0) {
    historyList.innerHTML = `<p style="color:var(--clr-muted)">No sessions yet.</p>`;
    return;
  }
  historyList.innerHTML = sessions.map(s => `
    <div class="card" style="margin-bottom:.75rem;padding:1rem">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div>
          <p style="font-weight:600">${new Date(s.started_at).toLocaleString()}</p>
          <p style="font-size:.85rem;color:var(--clr-muted)">
            ${s.ended_at ? "Ended " + new Date(s.ended_at).toLocaleTimeString() : "Active"}
            &nbsp;·&nbsp; ↑ IN: ${s.total_in ?? 0}  ↓ OUT: ${s.total_out ?? 0}
          </p>
        </div>
        <button class="btn btn-ghost" onclick="downloadCsv('${s.id}')">Export CSV</button>
      </div>
    </div>`).join("");
}

window.downloadCsv = async function(sessionId) {
  const res = await exportSession(sessionId);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = `session-${sessionId}.csv`;
  a.click(); URL.revokeObjectURL(url);
};

document.getElementById("close-history").addEventListener("click", () => historyModal.classList.add("hidden"));

importInput.addEventListener("change", async () => {
  const file = importInput.files[0];
  if (!file) return;
  try {
    await importProfile(file);
    importBanner.textContent = "Profile imported successfully!";
    importBanner.classList.remove("hidden");
    loadProfiles();
    setTimeout(() => importBanner.classList.add("hidden"), 4000);
  } catch (e) {
    alert("Import failed: " + e.message);
  }
  importInput.value = "";
});

function escHtml(s) {
  return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

loadProfiles();
</script>
</body>
</html>
```

- [ ] **Step 7.2 — Commit**

```bash
git add frontend/index.html
git commit -m "feat: redesign home page with app header and data-rich profile cards"
```

---

## Task 8: Redesign count page HTML (count.html)

**Files:**
- Modify: `frontend/count.html`

- [ ] **Step 8.1 — Replace count.html with redesigned version**

Replace the entire content of `frontend/count.html` with:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Live Counting — Doorway Counter</title>
  <link rel="stylesheet" href="/css/styles.css">
</head>
<body>
<div class="container" style="max-width:1100px">

  <!-- Header card -->
  <div class="count-header">
    <div class="header-left">
      <div class="live-dot" id="live-dot"></div>
      <div>
        <div class="profile-title" id="profile-name">Loading…</div>
        <div class="session-meta">
          <span id="session-timer">00:00</span>
          <span class="fps-badge" id="fps-badge">● LIVE</span>
        </div>
      </div>
    </div>
    <div class="header-right">
      <button class="btn btn-ghost" id="btn-flip">↔ Flip Direction</button>
      <button class="btn btn-ghost" id="btn-pause">⏸ Pause</button>
      <button class="btn btn-danger" id="btn-stop">■ Stop</button>
    </div>
  </div>

  <!-- Door opens banner -->
  <div id="door-banner" class="banner banner-warning hidden" style="margin-bottom:.75rem">
    ⚠️ This door opens randomly — accuracy may be reduced for up to 60 s after a door state change.
  </div>

  <!-- Count bar -->
  <div class="count-bar">
    <div class="count-cell in">
      <span class="count-label">↑ In</span>
      <span class="count-value" id="count-in">0</span>
      <span class="count-sub">people entered</span>
    </div>
    <div class="count-cell out">
      <span class="count-label">↓ Out</span>
      <span class="count-value" id="count-out">0</span>
      <span class="count-sub">people exited</span>
    </div>
    <div class="count-cell occ">
      <span class="count-label">= Occupancy</span>
      <span class="count-value" id="count-occ">0</span>
      <span class="count-sub">currently inside</span>
    </div>
  </div>

  <!-- Stream + overlay -->
  <div class="video-wrapper" style="margin-bottom:.75rem;border-radius:var(--radius-lg)">
    <img id="stream" alt="Live stream" style="background:#000">
    <div class="stream-badges">
      <span class="stream-badge">● LIVE</span>
    </div>
    <div id="stream-error" class="hidden" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.7);border-radius:var(--radius-lg)">
      <div style="text-align:center">
        <p style="color:var(--clr-error);margin-bottom:.75rem">Stream interrupted</p>
        <button class="btn btn-ghost" id="btn-reload-stream">Retry</button>
      </div>
    </div>
  </div>

  <!-- Bottom panel -->
  <div style="display:grid;grid-template-columns:1fr auto;gap:.75rem">
    <div class="card" style="padding:1rem">
      <h3 style="font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--clr-muted);margin-bottom:.75rem">Recent Events</h3>
      <div id="events-log" class="events-log"></div>
    </div>
    <div class="card" style="display:flex;flex-direction:column;gap:.45rem;min-width:155px;padding:1rem">
      <h3 style="font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--clr-muted);margin-bottom:.3rem">Actions</h3>
      <a href="/calibrate.html" class="btn btn-ghost" style="justify-content:center;font-size:.82rem">⚙ Recalibrate</a>
      <button class="btn btn-ghost" id="btn-export" style="justify-content:center;font-size:.82rem">📋 Export CSV</button>
      <button class="btn btn-ghost" id="btn-grayscale" style="justify-content:center;font-size:.82rem">🔲 Grayscale</button>
      <a href="/" class="btn btn-ghost" style="justify-content:center;font-size:.82rem">🚪 Switch Door</a>
    </div>
  </div>

  <!-- Reconnecting banner -->
  <div id="reconnect-banner" class="banner banner-info hidden" style="margin-top:.75rem">
    WebSocket disconnected — reconnecting…
  </div>
</div>

<!-- Stop confirmation modal -->
<div id="stop-backdrop" class="modal-backdrop hidden"></div>
<div id="stop-modal" class="modal hidden">
  <h2 style="font-size:1.1rem;margin-bottom:.5rem">Stop counting session?</h2>
  <p style="color:var(--clr-muted);font-size:.9rem;margin-bottom:1.25rem">
    The camera will be released and you'll return to the profile list.
  </p>
  <div style="display:flex;gap:.75rem;justify-content:flex-end">
    <button class="btn btn-ghost" id="btn-stop-cancel">Cancel</button>
    <button class="btn btn-danger" id="btn-stop-confirm">Stop &amp; Exit</button>
  </div>
</div>

<script type="module" src="/js/count.js"></script>
</body>
</html>
```

- [ ] **Step 8.2 — Commit**

```bash
git add frontend/count.html
git commit -m "feat: redesign count page with header card, tinted count cells, stream badges"
```

---

## Task 9: Update count.js — session timer, auto-retry (already in Task 3), new DOM refs

**Files:**
- Modify: `frontend/js/count.js`

*(Auto-retry was already added in Task 3. This task adds the session timer and wires the new DOM elements.)*

- [ ] **Step 9.1 — Add sessionStart tracking and timer**

In `count.js`, after `let grayscaleOn = false;`, add:

```javascript
let sessionStart = null;
let timerInterval = null;
```

- [ ] **Step 9.2 — Add formatTimer utility**

After the existing `let wsRetries` declarations add:

```javascript
function formatTimer(ms) {
  const total = Math.floor(ms / 1000);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${String(h).padStart(2,"0")}:${mm}:${ss}` : `${mm}:${ss}`;
}
```

- [ ] **Step 9.3 — Update init() to start timer**

In `init()`, after `sessionId = session.session_id;`, add:

```javascript
  sessionStart = new Date(session.started_at);
  const timerEl = document.getElementById("session-timer");
  if (timerEl) {
    timerInterval = setInterval(() => {
      timerEl.textContent = formatTimer(Date.now() - sessionStart);
    }, 1000);
  }
```

- [ ] **Step 9.4 — Clear timer on stop**

In `btnStopConfirm`'s click listener, before `if (sessionId) await endSession(...)`, add:

```javascript
  if (timerInterval) clearInterval(timerInterval);
```

- [ ] **Step 9.5 — Update DOM element IDs that changed**

The new count.html uses `class="profile-title"` on the name element. Verify the existing query `document.getElementById("profile-name")` still works — the new HTML has `id="profile-name"` on that element, so no change needed.

Check that `document.getElementById("fps-badge")` is queried and can be updated with FPS info via WebSocket ping messages if desired. For now, the badge just shows "● LIVE" statically — no change needed to JS.

- [ ] **Step 9.6 — Commit**

```bash
git add frontend/js/count.js
git commit -m "feat: add session timer to count page"
```

---

## Task 10: Redesign calibration wizard HTML (calibrate.html named progress bar)

**Files:**
- Modify: `frontend/calibrate.html`

*(This task updates the step cards' visual styling. Step removal and renumbering was done in Task 5.)*

- [ ] **Step 10.1 — Add step-num-label to each step card header**

In each active step div, add a `<div class="step-num-label">Step N of 8</div>` above the `<h2>` in each `.step-header`. Example for step 1:

```html
<div class="step-header">
  <div class="step-num-label">Step 1 of 8</div>
  <h2>Allow Camera Access</h2>
  <p>We need your camera to see the doorway</p>
</div>
```

Do this for all 8 steps (step-1 through step-8). Step numbers: 1=Camera, 2=Preview, 3=Capture, 4=Quality, 5=Boundary, 6=Draw, 7=Door, 8=Save.

- [ ] **Step 10.2 — Update step-progress class to named-progress**

The `id="step-dots"` container should already have been changed to `class="named-progress"` in Task 5. Confirm it reads:

```html
<div class="named-progress" id="step-dots"></div>
```

- [ ] **Step 10.3 — Commit**

```bash
git add frontend/calibrate.html
git commit -m "feat: add step-num labels to calibration wizard step cards"
```

---

## Task 11: Final check — run full test suite

- [ ] **Step 11.1 — Run complete test suite with coverage**

```
pytest --cov=backend tests/ -v
```

Expected: all tests pass, no regressions.

- [ ] **Step 11.2 — Fix any failures before proceeding**

If tests fail, investigate the specific failure before continuing. Common causes:
- DOM element ID changes in HTML that break existing integration tests
- Import errors from removed functions

- [ ] **Step 11.3 — Commit any test fixes**

```bash
git add -A
git commit -m "test: fix any test regressions after redesign"
```

- [ ] **Step 11.4 — Run the app and manually verify**

```
python run.py
```

Open http://localhost:8000 and verify:
1. Home page shows app header + profile cards with stats
2. Create a new profile — wizard shows named progress bar, no video option
3. After saving profile, count page loads (may take 1-2 s — auto-retry handles it)
4. Count page shows header with timer, tinted count cells, stream
5. Stop button shows confirmation modal, returns to home page
6. Home page shows updated stats after stopping session

---

## Dependency Order

```
Task 1 (stop fix) → independent
Task 2 (stream TOCTOU) → independent
Task 3 (frontend delay/retry) → independent
Task 4 (profiles stats) → independent
Task 5 (video removal) → after Task 4 (same file calibrate.js but compatible)
Task 6 (CSS) → after Tasks 1-4 (provides classes for Tasks 7-10)
Task 7 (index.html) → after Tasks 4, 6
Task 8 (count.html) → after Task 6
Task 9 (count.js) → after Tasks 3, 8
Task 10 (calibrate.html) → after Tasks 5, 6
Task 11 (full test) → after all tasks
```

Tasks 1-5 can all run in parallel. Tasks 6-10 can run in parallel after Task 6's CSS is done.
