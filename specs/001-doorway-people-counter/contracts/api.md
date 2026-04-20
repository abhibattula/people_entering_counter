# API Contract: Doorway People Counter

**Phase**: 1 — Design & Contracts
**Date**: 2026-04-20
**Base URL**: `http://localhost:8000`

---

## Calibration Endpoints

### POST /api/calibrate/frames

Submit captured frames for doorway detection and quality assessment.

**Request**: `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `frames` | File[] | Yes | JPEG images (1–15 files) |
| `mode` | string | Yes | `"video"` or `"photo"` |

**Response 200**:
```json
{
  "quality_check": {
    "door_fully_visible": true,
    "lighting_acceptable": true,
    "crowding_risk": "low",
    "camera_adjustment": "keep"
  },
  "proposal": {
    "roi_polygon": [[210,40],[430,40],[430,320],[210,320]],
    "counting_line": { "x1": 210, "y1": 180, "x2": 430, "y2": 180 },
    "inside_direction": "up",
    "confidence": 0.87,
    "best_frame_b64": "<base64 JPEG string>"
  }
}
```

**Response 422**: Frame count out of range, invalid mode, corrupt image files.
**Response 503**: YOLOv8 model not yet loaded.

---

### POST /api/calibrate/retry

Re-attempt doorway proposal with the same frames (up to 2 retries).

**Request**: `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `frames` | File[] | Yes | Same or different JPEG frames |
| `mode` | string | Yes | `"video"` or `"photo"` |

**Response**: identical schema to `POST /api/calibrate/frames`
**Response 429**: More than 2 retries attempted for this set of frames.

---

## Profile Endpoints

### GET /api/profiles

List all saved door profiles.

**Response 200**:
```json
[
  { "id": "uuid", "name": "Main Entrance", "created_at": "2026-04-20T14:30:00Z" },
  { "id": "uuid", "name": "Side Door", "created_at": "2026-04-20T15:00:00Z" }
]
```

---

### POST /api/profiles

Save a confirmed door profile.

**Request**: `application/json`
```json
{
  "name": "Main Entrance",
  "camera_index": 0,
  "capture_mode": "photo",
  "frame_width": 1280,
  "frame_height": 720,
  "roi_polygon": [[210,40],[430,40],[430,320],[210,320]],
  "counting_line": { "x1": 210, "y1": 180, "x2": 430, "y2": 180 },
  "inside_direction": "up",
  "door_randomly_opens": false,
  "quality_check": {
    "door_fully_visible": true,
    "lighting_acceptable": true,
    "crowding_risk": "low",
    "camera_adjustment": "keep"
  }
}
```

**Response 201**:
```json
{ "id": "uuid-v4", "created_at": "2026-04-20T14:30:00Z" }
```

**Response 422**: Validation failure (invalid polygon, name too long, etc.)

---

### GET /api/profiles/{id}

Return the full profile JSON.

**Response 200**: Full `DoorProfile` object (see data-model.md)
**Response 404**: Profile not found.

---

### GET /api/profiles/{id}/export

Download the profile as a JSON file (for backup or transfer to another machine).

**Response 200**:
```
Content-Type: application/json
Content-Disposition: attachment; filename="profile-{name}.json"
```
Body: full `DoorProfile` JSON object.

**Response 404**: Profile not found.

---

### POST /api/profiles/import

Import a previously exported profile JSON file.

**Request**: `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | File | Yes | A `.json` file previously exported via `GET /api/profiles/{id}/export` |

**Response 201**:
```json
{ "id": "new-uuid-v4", "created_at": "2026-04-20T14:30:00Z" }
```
A new UUID is assigned on import — the original ID from the exported file is not reused.

**Response 422**: Invalid JSON, missing required fields, or schema validation failure.

---

### DELETE /api/profiles/{id}

Delete a profile and all its associated session events.

**Response 204**: Deleted successfully.
**Response 404**: Profile not found.
**Response 409**: Profile is currently active in a counting session.

---

## Live Counting Endpoints

### GET /stream

Stream annotated MJPEG video for the active profile.

**Query params**:
| Param | Type | Required | Description |
|---|---|---|---|
| `profile_id` | string | Yes | UUID of the profile to stream |

**Response**: `Content-Type: multipart/x-mixed-replace; boundary=frame`

Each part is a JPEG frame with OpenCV-rendered overlays:
- Purple dashed polygon = ROI boundary
- Yellow dashed line = counting line
- Green bounding boxes = tracked persons
- Direction arrow at counting line midpoint

**Response 404**: Profile not found.
**Response 503**: Camera unavailable.

---

### WebSocket /ws/counts

Receive real-time crossing events.

**Query params**:
| Param | Type | Required | Description |
|---|---|---|---|
| `profile_id` | string | Yes | UUID of the active profile |

**Server → Client message** (JSON, sent on each crossing):
```json
{
  "direction": "in",
  "occupancy": 5,
  "timestamp": "2026-04-20T14:32:07.123Z"
}
```

**Client → Server**: no messages expected; connection is receive-only.
**Close codes**: `1001` = profile stopped · `1011` = camera error

---

## Session Endpoints

### POST /api/sessions/start

Begin a new counting session for a profile.

**Request**:
```json
{ "profile_id": "uuid" }
```

**Response 201**:
```json
{ "session_id": "uuid", "started_at": "2026-04-20T14:30:00Z" }
```

**Response 409**: A session for this profile is already active.

---

### POST /api/sessions/{id}/end

End an active session.

**Response 204**: Session closed.
**Response 404**: Session not found.

---

### GET /api/sessions/{id}/events

List all crossing events for a session.

**Response 200**:
```json
[
  { "id": 1, "timestamp": "2026-04-20T14:32:07Z", "direction": "in", "occupancy": 1 },
  { "id": 2, "timestamp": "2026-04-20T14:33:15Z", "direction": "out", "occupancy": 0 }
]
```

---

### GET /api/sessions/{id}/export

Download session events as CSV.

**Response 200**:
```
Content-Type: text/csv
Content-Disposition: attachment; filename="session-{id}.csv"

id,timestamp,direction,occupancy
1,2026-04-20T14:32:07Z,in,1
2,2026-04-20T14:33:15Z,out,0
```

---

## System Endpoints

### GET /api/health

Check system readiness.

**Response 200**:
```json
{
  "status": "ok",
  "model_loaded": true,
  "camera_available": true
}
```

---

### GET /api/cameras

List available camera devices.

**Response 200**:
```json
[
  { "index": 0, "name": "Integrated Webcam", "resolution": "1280x720" },
  { "index": 1, "name": "USB Camera", "resolution": "1920x1080" }
]
```

---

## Error Response Format

All error responses use this shape:
```json
{
  "detail": "Human-readable error message"
}
```

HTTP status codes follow REST conventions: 200/201/204 success · 404 not found · 409 conflict · 422 validation · 429 rate limit · 503 service unavailable.
