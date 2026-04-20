# Doorway People Counter System — Design Spec
**Date:** 2026-04-20  
**Status:** Approved  
**Stack:** Python (FastAPI + YOLOv8 + OpenCV) · Vanilla JS/HTML/CSS · SQLite + JSON

---

## 1. Context

A local browser-deployed people counter for doorways and entryways. The user sets up the system by pointing their laptop webcam at a doorway; the system guides them through calibration, proposes a doorway boundary automatically, then runs real-time IN/OUT counting using YOLOv8 object detection. All data stays on the user's machine — no cloud dependency.

---

## 2. System Architecture

**Approach: Hybrid camera ownership**

- **Calibration phase:** Browser controls camera via `getUserMedia()`. Captures frames (video clip or guided photos), POSTs them to FastAPI. YOLOv8 analyses the frames server-side and returns a doorway boundary proposal.
- **Live counting phase:** Browser releases `getUserMedia`. Python/OpenCV opens the same camera. YOLOv8 + ByteTrack run per frame. Annotated MJPEG stream sent to browser; crossing events sent over WebSocket.

```
┌─────────────────────────────────────────────────────────────┐
│                     BROWSER (Vanilla JS)                    │
│  ┌─────────────────────┐   ┌───────────────────────────┐   │
│  │   Calibration UI    │   │     Live Counting UI      │   │
│  │  (getUserMedia)     │   │   MJPEG stream + WS feed  │   │
│  └────────┬────────────┘   └────────────┬──────────────┘   │
│           │ REST (POST frames)           │ WS + MJPEG       │
└───────────┼──────────────────────────────┼──────────────────┘
            │                              │
┌───────────▼──────────────────────────────▼──────────────────┐
│                    FastAPI Backend (Python)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Calibration │  │  Counting    │  │  Profile Manager │  │
│  │  Service     │  │  Service     │  │  (JSON files)    │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────┘  │
│  ┌──────▼─────────────────▼───────┐  ┌──────────────────┐  │
│  │      YOLOv8 Model Singleton    │  │  Count History   │  │
│  │   (shared ultralytics instance)│  │  (SQLite)        │  │
│  └────────────────────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
            │
┌───────────▼─────────┐
│  System Camera      │
│  (OpenCV - runtime) │
└─────────────────────┘
```

**Key boundaries:**
- YOLOv8 loaded once at startup, shared between calibration and counting
- Camera ownership transfers from browser → Python at the end of calibration
- Profiles stored as `profiles/{uuid}.json`; count history in SQLite

---

## 3. Calibration Wizard (9 Steps)

### Step 1 — Camera Permission
- Call `getUserMedia({ video: true })`
- On deny: show instructions to enable in browser settings, block wizard progress
- On grant: proceed immediately

### Step 2 — Live Preview
- Full-width `<video>` element showing camera feed
- Overlay grid guide to help user frame the doorway
- Instruction: "Point camera at the full doorway, keep it steady"

### Step 3 — Capture Mode Selection
- Two options: **📹 5-second video clip** | **📷 5-photo guided capture** (labelled "more accurate")

### Step 4 — Capture

**Video mode:**
- 3-2-1 countdown overlay → 5-second recording via `MediaRecorder`
- Extract 15 frames evenly spaced from the clip client-side

**Photo mode (5 shots):**
1. Center view
2. Slightly left
3. Slightly right
4. Up / down adjustment
5. Final counting position

Each shot: position instruction text + "Capture" button + thumbnail confirmation before proceeding.

### Step 5 — Placement Quality Check
Shown immediately after capture, before analysis proceeds. User can re-capture or override and continue.

| Indicator | Values |
|---|---|
| Door fully visible | yes / no |
| Lighting acceptable | yes / no |
| Crowding risk | low / medium / high |
| Camera adjustment | move closer / move farther / keep current |

Quality is assessed by `quality_service.py` against the captured frames using heuristics (brightness histogram, edge detection for door frame coverage, frame occupancy density).

### Step 6 — Doorway Proposal
Display best-quality frame with overlaid:
- **Green polygon** — proposed doorway ROI boundary
- **Yellow dashed line** — proposed counting line (horizontal midpoint of ROI)
- **Purple arrow** — inside/outside direction candidate

Detection approach: YOLOv8 person detections across all frames + edge/contour detection to identify rectangular door frame region. The ROI polygon is the convex hull of the detected door frame.

### Step 7 — User Confirmation (3 sub-steps)
1. "Is this the door?" → **Yes** / **No**
2. "Is this outline correct?" → **Yes** / **Adjust** (drag handles to reposition polygon corners)
3. "Which direction is INSIDE?" → **Flip** / **Confirm** (arrow animation shows direction)

On any rejection: retry auto-proposal (max 2 retries). After 2 failed retries: unlock **manual fallback** — user draws polygon and counting line directly on canvas.

### Step 8 — Door Behavior Question
"Is this door opened and closed randomly?"
- **Yes:** display persistent warning banner during counting: "Door state changes detected — model may take up to 1 minute to adapt before accurate counting resumes."
- **No:** no warning needed

### Step 9 — Save & Start
- POST profile to `/api/profiles`
- Browser calls `stream.getTracks().forEach(t => t.stop())` to release camera
- Navigate to `count.html?profile_id={id}`
- Python/OpenCV opens camera; MJPEG stream and WebSocket connect
- Counter initialises at 0 IN / 0 OUT

---

## 4. Live Counting View

### Layout
```
┌─────────────────────────────────────────────┐
│ ● Live · Main Entrance     [⏸ Pause][■ Stop]│
├─────────────────────────────────────────────┤
│                                             │
│          MJPEG stream (16:9)                │
│   [ROI polygon][counting line][boxes]       │
│                          24fps · YOLOv8n    │
├───────────────┬─────────────┬───────────────┤
│  24 ↑ IN      │  19 ↓ OUT   │  5 = OCCUPANCY│
├───────────────┴─────────────┴───────────────┤
│ Recent Events          │ ⚙ Recalibrate      │
│ ↑ IN  14:32:07         │ 📋 Export CSV       │
│ ↓ OUT 14:31:58         │ 🚪 Switch Door      │
└────────────────────────┴────────────────────┘
```

### Counting Logic
- YOLOv8n (nano — fastest variant) runs per frame on ROI-masked region
- ByteTrack assigns persistent IDs to tracked persons across frames
- Line crossing detected when a tracked person's centroid trajectory crosses the counting line
- Direction determined by which side of the line the centroid was on in the previous frame
- Occupancy = cumulative IN − cumulative OUT (floored at 0)

### Stream delivery
- **Video:** `<img>` element with `src="/stream?profile_id={id}"` — MJPEG (multipart/x-mixed-replace)
- **Counts:** WebSocket `/ws/counts?profile_id={id}` emits per crossing: `{ direction, occupancy, timestamp }`
- Annotations (ROI polygon, counting line, bounding boxes) rendered server-side on MJPEG frames via OpenCV `cv2.draw*`

---

## 5. Data Models

### Profile — `profiles/{uuid}.json`
```json
{
  "id": "uuid-v4",
  "name": "Main Entrance",
  "created_at": "2026-04-20T14:30:00Z",
  "camera_index": 0,
  "capture_mode": "photo",
  "roi_polygon": [[x1,y1],[x2,y2],[x3,y3],[x4,y4]],
  "counting_line": { "x1": 210, "y1": 180, "x2": 430, "y2": 180 },
  "inside_direction": "up",  // "up" | "down" | "left" | "right"
  "door_randomly_opens": true,
  "frame_width": 1280,
  "frame_height": 720,
  "quality_check": {
    "door_fully_visible": true,
    "lighting_acceptable": true,
    "crowding_risk": "low",
    "camera_adjustment": "keep"
  }
}
```

### SQLite — `data/counts.db`

**`sessions` table**
```sql
CREATE TABLE sessions (
  id         TEXT PRIMARY KEY,
  profile_id TEXT NOT NULL,
  started_at DATETIME NOT NULL,
  ended_at   DATETIME
);
```

**`events` table**
```sql
CREATE TABLE events (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  profile_id TEXT NOT NULL,
  timestamp  DATETIME NOT NULL,
  direction  TEXT NOT NULL CHECK(direction IN ('in','out')),
  occupancy  INTEGER NOT NULL
);
```

---

## 6. API Contracts

### Calibration
```
POST /api/calibrate/frames
  Body:    multipart — { frames: File[], mode: "video"|"photo" }
  Returns: { quality_check, proposal: { roi_polygon, counting_line,
             inside_direction, best_frame_b64 } }

POST /api/calibrate/retry
  Body:    { frames: File[], mode: "video"|"photo" }
  Returns: same as above

POST /api/profiles
  Body:    { name, camera_index, roi_polygon, counting_line,
             inside_direction, door_randomly_opens,
             quality_check, frame_width, frame_height }
  Returns: { id, created_at }

GET    /api/profiles          → [{ id, name, created_at }]
GET    /api/profiles/{id}     → full profile JSON
DELETE /api/profiles/{id}     → 204 No Content
```

### Live Counting
```
GET  /stream?profile_id={id}          → MJPEG (multipart/x-mixed-replace)
WS   /ws/counts?profile_id={id}       → { direction, occupancy, timestamp }

POST /api/sessions/start              Body: { profile_id } → { session_id }
POST /api/sessions/{id}/end           → 204 No Content
GET  /api/sessions/{id}/events        → [{ id, timestamp, direction, occupancy }]
GET  /api/sessions/{id}/export        → CSV download (Content-Disposition: attachment)
```

### System
```
GET  /api/health     → { status, model_loaded, camera_available }
GET  /api/cameras    → [{ index, name, resolution }]
```

---

## 7. Project File Structure

```
doorway-counter/
├── backend/
│   ├── main.py                   # FastAPI app, mounts routes, serves static
│   ├── config.py                 # paths, camera index, model variant
│   ├── routers/
│   │   ├── calibration.py        # POST /api/calibrate/*
│   │   ├── profiles.py           # CRUD /api/profiles
│   │   ├── stream.py             # GET /stream MJPEG
│   │   ├── counts.py             # WS /ws/counts
│   │   └── sessions.py           # session lifecycle + export
│   ├── services/
│   │   ├── calibration_service.py  # frame analysis, ROI proposal algorithm
│   │   ├── counting_service.py     # OpenCV loop, ByteTrack, line crossing
│   │   ├── quality_service.py      # placement quality heuristics
│   │   └── model_service.py        # YOLOv8 singleton (loaded once)
│   ├── db/
│   │   ├── database.py           # SQLite connection, CREATE TABLE on init
│   │   └── models.py             # Session, Event dataclasses
│   └── profiles/                 # JSON profile store (gitignored)
│       └── {uuid}.json
├── frontend/
│   ├── index.html                # profile list + "Create New" entry point
│   ├── calibrate.html            # calibration wizard (9 steps)
│   ├── count.html                # live counting view
│   ├── js/
│   │   ├── calibrate.js          # wizard state machine, getUserMedia, canvas
│   │   ├── count.js              # MJPEG img src swap, WebSocket client
│   │   ├── api.js                # fetch wrapper for all backend calls
│   │   └── utils.js              # canvas drawing helpers, quality badge render
│   └── css/
│       └── styles.css            # single stylesheet
├── data/
│   └── counts.db                 # SQLite (gitignored)
├── requirements.txt              # fastapi, uvicorn, ultralytics, opencv-python, aiofiles
├── run.py                        # python run.py → starts uvicorn on :8000
└── README.md
```

`.gitignore` must include: `backend/profiles/`, `data/`, `.superpowers/`

---

## 8. Error States & Edge Cases

### Camera errors
| Situation | Behavior |
|---|---|
| User denies camera permission | Instructions to enable in browser settings; wizard blocked |
| Camera in use by another app | Error banner + retry button |
| Camera disconnected mid-session | Pause counting, reconnect prompt, auto-resume |
| OpenCV fails to open camera | Prompt to select different camera index via `/api/cameras` |

### Calibration errors
| Situation | Behavior |
|---|---|
| No doorway detected in frames | "No doorway detected" → retry capture or manual drawing |
| Auto-proposal rejected twice | Unlock manual fallback: drag polygon corners + line on canvas |
| Quality check fails | Warning shown; user can re-capture or override and continue |
| Frame upload fails | Inline error + retry; frames held in JS memory |

### Runtime counting errors
| Situation | Behavior |
|---|---|
| WebSocket disconnects | Auto-reconnect with 3 s backoff; "Reconnecting…" banner |
| MJPEG stream stalls | Reload `<img>` src with cache-bust; stale frame indicator |
| Inference too slow (<10 fps) | Warning badge: "Processing slow — consider switching to YOLOv8n" |
| Door randomly opens (flagged) | Adaptation warning; counts may be unreliable for up to 60 s |
| Occupancy goes negative | Floor at 0; log anomaly to SQLite; show warning badge |

### Data errors
| Situation | Behavior |
|---|---|
| Profile JSON corrupted | Skip on load; show "Profile unreadable" in list with delete option |
| SQLite locked | Queue writes; retry after 100 ms; surface error after 3 failures |
| Disk full | Stop counting; show error; offer CSV export of in-memory events |

---

## 9. Real-World Behaviour Notes

- **Person far from door:** detected by YOLOv8 but outside ROI polygon — excluded from tracking pipeline entirely
- **25–40% frame coverage:** ideal range for YOLOv8 detection; quality check warns if coverage falls outside 20–60%
- **Simultaneous crossings:** handled by ByteTrack multi-object tracker (built into Ultralytics)
- **Partial occlusion:** tracked if >50% of person bounding box is within frame; missed if mostly occluded
- **Crowded doorway (3+ overlapping people):** accuracy degrades; crowding risk indicator warns user at setup
- **Retraining:** not required — ROI masking + line-crossing covers all realistic scenarios without model fine-tuning

---

## 10. Verification Checklist

### Calibration
- [ ] `getUserMedia` permission request fires on "Create New Profile" click
- [ ] Live preview displays in browser within 1 second of permission grant
- [ ] Video mode: 15 frames extracted from 5-second clip and POSTed to `/api/calibrate/frames`
- [ ] Photo mode: all 5 guided positions shown with instructions; thumbnails confirm each
- [ ] Quality check results displayed before proposal is shown
- [ ] Doorway polygon and counting line rendered on best frame image
- [ ] Rejection → retry → second rejection → manual drawing mode unlocked
- [ ] Profile saved to `profiles/{uuid}.json` with all fields populated
- [ ] Browser camera released before navigating to count view

### Live Counting
- [ ] MJPEG stream loads within 2 seconds of page open
- [ ] WebSocket connects and emits events on each crossing
- [ ] IN count increments when person crosses line toward "inside" direction
- [ ] OUT count increments for the reverse direction
- [ ] Occupancy = IN − OUT, floored at 0
- [ ] Pause stops stream and freezes counts; resume restarts both
- [ ] Export CSV contains all events for the session with correct timestamps
- [ ] Recalibrate button releases OpenCV camera and re-launches wizard

### Error paths
- [ ] Camera denial shows actionable instructions
- [ ] WebSocket disconnect triggers auto-reconnect banner
- [ ] MJPEG stall triggers stream reload
- [ ] Corrupted profile shows "unreadable" state in profile list, not crash
