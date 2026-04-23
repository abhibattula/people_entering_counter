# API Contract Delta: UI Redesign, Bug Fixes & Video Mode Removal

**Phase**: 1 — Design & Contracts
**Date**: 2026-04-22
**Base**: `specs/001-doorway-people-counter/contracts/api.md`

This document describes **only the changes** to the existing API contract. All endpoints not listed here are unchanged.

---

## Changed Endpoints

### GET /api/profiles

**Change**: Each profile object in the response array now includes three additional integer fields.

**New response fields** (per profile object):

| Field | Type | Description |
|---|---|---|
| `session_count` | `integer` | Number of sessions ever started for this profile |
| `total_in` | `integer` | Lifetime total of IN crossing events across all sessions |
| `total_out` | `integer` | Lifetime total of OUT crossing events across all sessions |

**Example response object (additions highlighted)**:

```json
{
  "id": "3f2a...",
  "name": "Main Entrance",
  "camera_index": 0,
  "created_at": "2026-04-22T10:00:00Z",
  "session_count": 5,
  "total_in": 142,
  "total_out": 138
}
```

**Backward compatibility**: These fields are additive. Existing clients that do not read them are unaffected. Profiles with no sessions return `session_count=0, total_in=0, total_out=0`.

**Error cases**: Unchanged — returns `[]` if no profiles exist.

---

### GET /stream

**No change** to the stream endpoint beyond what was already documented in `specs/002-fix-detection-visibility/contracts/api.md` (the `grayscale` query parameter added in that release). The TOCTOU pre-check removal in `stream.py` is an internal implementation fix; the API contract is unchanged.

---

## Removed Internal Behaviour (not a public API change)

### stream.py — TOCTOU pre-check removed

The internal `cv2.VideoCapture` probe that previously ran inside `mjpeg_stream()` before the MJPEG generator is removed. This has no effect on the HTTP contract — the endpoint still returns `multipart/x-mixed-replace` frames or closes the connection if the camera is unavailable.

---

## Unchanged Endpoints (reference)

All other endpoints from `specs/001-doorway-people-counter/contracts/api.md` and `specs/002-fix-detection-visibility/contracts/api.md` remain unchanged:

- `POST /api/calibrate/frames`
- `POST /api/calibrate/retry`
- `POST /api/profiles`
- `GET /api/profiles/{id}`
- `GET /api/profiles/{id}/export`
- `POST /api/profiles/import`
- `DELETE /api/profiles/{id}`
- `WS /ws/counts`
- `POST /api/sessions/start`
- `POST /api/sessions/{id}/end`
- `POST /api/sessions/{id}/pause`
- `POST /api/sessions/{id}/resume`
- `GET /api/sessions`
- `GET /api/sessions/{id}/events`
- `GET /api/sessions/{id}/export`
- `GET /api/health`
- `GET /api/cameras`
- `GET /stream` (grayscale param unchanged from 002)
