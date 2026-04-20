# Data Model: Doorway People Counter

**Phase**: 1 — Design & Contracts
**Date**: 2026-04-20

---

## Entity 1: DoorProfile

**Storage**: `backend/profiles/{id}.json` (one file per profile)
**Created by**: `POST /api/profiles` (end of calibration wizard)
**Read by**: profile list, counting service, stream service

```json
{
  "id": "string (UUID v4)",
  "name": "string — human label, e.g. 'Main Entrance'",
  "created_at": "string (ISO 8601 datetime)",
  "camera_index": "integer — OpenCV device index, default 0",
  "capture_mode": "string — 'photo' | 'video'",
  "frame_width": "integer — pixels, e.g. 1280",
  "frame_height": "integer — pixels, e.g. 720",
  "roi_polygon": [
    [x1, y1],
    [x2, y2],
    [x3, y3],
    [x4, y4]
  ],
  "counting_line": {
    "x1": "integer",
    "y1": "integer",
    "x2": "integer",
    "y2": "integer"
  },
  "inside_direction": "string — 'up' | 'down' | 'left' | 'right'",
  "door_randomly_opens": "boolean",
  "quality_check": {
    "door_fully_visible": "boolean",
    "lighting_acceptable": "boolean",
    "crowding_risk": "string — 'low' | 'medium' | 'high'",
    "camera_adjustment": "string — 'keep' | 'closer' | 'farther'"
  }
}
```

**Validation rules**:
- `name`: 1–100 characters, non-empty
- `roi_polygon`: exactly 4 points, each `[x, y]` within `[0, frame_width]` × `[0, frame_height]`
- `counting_line`: both endpoints must fall within the ROI bounding box
- `inside_direction`: must be one of the four enum values
- `camera_index`: non-negative integer

---

## Entity 2: Session

**Storage**: `data/counts.db`, table `sessions`
**Created by**: `POST /api/sessions/start`
**Closed by**: `POST /api/sessions/{id}/end`

| Column | Type | Constraints |
|---|---|---|
| `id` | TEXT | PRIMARY KEY (UUID v4) |
| `profile_id` | TEXT | NOT NULL, FK → profile JSON file |
| `started_at` | DATETIME | NOT NULL |
| `ended_at` | DATETIME | NULL until session ends |

**State transitions**:
```
created (started_at set, ended_at NULL)
    → active (counting running)
    → closed (ended_at set on POST /end)
```

---

## Entity 3: CrossingEvent

**Storage**: `data/counts.db`, table `events`
**Created by**: `counting_service.py` on each line crossing
**Read by**: `GET /api/sessions/{id}/events` and CSV export

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `session_id` | TEXT | NOT NULL, FK → sessions.id |
| `profile_id` | TEXT | NOT NULL |
| `timestamp` | DATETIME | NOT NULL (UTC) |
| `direction` | TEXT | NOT NULL, CHECK IN ('in', 'out') |
| `occupancy` | INTEGER | NOT NULL, ≥ 0 |

**Business rules**:
- `occupancy` is the running net total (IN − OUT) at the moment this event is recorded
- `occupancy` is floored at 0 — it can never go negative in storage
- Each row is immutable after insert

---

## Entity 4: PlacementQualityAssessment

**Storage**: embedded in DoorProfile.quality_check (not a separate entity)
**Computed by**: `quality_service.py` from captured frames
**Shown**: at Step 5 of calibration wizard before doorway proposal

| Field | Type | Values | Meaning |
|---|---|---|---|
| `door_fully_visible` | boolean | true / false | Door frame reaches ≥2 frame edges |
| `lighting_acceptable` | boolean | true / false | Mean L-channel brightness 60–230 |
| `crowding_risk` | string | low / medium / high | Avg persons per frame <1.5 / 1.5–3 / >3 |
| `camera_adjustment` | string | keep / closer / farther | ROI area 15–65% of frame = keep |

---

## Entity 5: CalibrationProposal (transient, not persisted)

**Lifetime**: lives only in the `POST /api/calibrate/frames` response; discarded after user confirms or rejects
**Purpose**: carry the system's doorway detection result from backend to browser

```json
{
  "quality_check": { /* PlacementQualityAssessment */ },
  "proposal": {
    "roi_polygon": [[x1,y1],[x2,y2],[x3,y3],[x4,y4]],
    "counting_line": { "x1": 0, "y1": 0, "x2": 0, "y2": 0 },
    "inside_direction": "up",
    "confidence": "float 0.0–1.0 — how certain the algorithm is",
    "best_frame_b64": "string — base64 JPEG of the highest-quality captured frame with proposal overlay"
  }
}
```

---

## SQLite Schema (complete DDL)

```sql
CREATE TABLE IF NOT EXISTS sessions (
  id         TEXT PRIMARY KEY,
  profile_id TEXT NOT NULL,
  started_at DATETIME NOT NULL,
  ended_at   DATETIME
);

CREATE TABLE IF NOT EXISTS events (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL REFERENCES sessions(id),
  profile_id TEXT NOT NULL,
  timestamp  DATETIME NOT NULL,
  direction  TEXT NOT NULL CHECK(direction IN ('in', 'out')),
  occupancy  INTEGER NOT NULL CHECK(occupancy >= 0)
);

CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
```
