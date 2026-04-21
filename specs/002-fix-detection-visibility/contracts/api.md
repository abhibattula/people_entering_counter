# API Contract Delta: Detection Accuracy & Visual Clarity Fixes

**Phase**: 1 — Design & Contracts
**Date**: 2026-04-21
**Base**: `specs/001-doorway-people-counter/contracts/api.md`

This document describes **only the changes** to the existing API contract. All endpoints not listed here are unchanged.

---

## Changed Endpoints

### GET /stream

**Change**: Added optional `grayscale` query parameter.

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `profile_id` | string | Yes | — | UUID of the profile to stream (unchanged) |
| `grayscale` | boolean string | No | `false` | When `"true"`, stream frames are converted to black-and-white after overlay rendering |

**Behaviour**:
- `grayscale=true` → each MJPEG frame is a greyscale JPEG (visually B&W, still encoded as 3-channel BGR with R=G=B)
- All overlays (door boundary, counting line, person boxes) remain visible in their original colours because they are applied before the greyscale conversion
- The client can change the value by reloading the stream URL with a different parameter value
- The grayscale state is per-stream-connection; it does not modify the stored profile

**Response format**: unchanged (`multipart/x-mixed-replace; boundary=frame`)

**Response 503**: unchanged (camera unavailable)

---

## Unchanged Endpoints (reference)

All other endpoints from `specs/001-doorway-people-counter/contracts/api.md` remain unchanged:

- `POST /api/calibrate/frames`
- `POST /api/calibrate/retry`
- `GET /api/profiles`
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
