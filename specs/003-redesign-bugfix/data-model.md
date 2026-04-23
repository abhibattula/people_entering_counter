# Data Model: UI Redesign, Bug Fixes & Video Mode Removal

**Phase**: 1 — Design & Contracts
**Date**: 2026-04-22
**Feature**: [spec.md](./spec.md)

---

## Changes to Existing Entities

### Door Profile (profile JSON — no schema migration)

The profile JSON schema is unchanged. The `capture_mode` field is retained for backward compatibility; new profiles always write `"photo"`.

| Field | Type | Existing Behaviour | Change |
|---|---|---|---|
| `capture_mode` | `string` | `"photo"` or `"video"` | New profiles always write `"photo"`; existing `"video"` profiles load without error |
| `frame_width` | `int` | Camera width in pixels | Unchanged |
| `frame_height` | `int` | Camera height in pixels | Unchanged |
| `inside_direction` | `string` | `"up"` / `"down"` / `"left"` / `"right"` | Unchanged |

No new profile JSON fields. No migration script needed.

---

## New API Response Fields (transient — not stored)

### GET /api/profiles — profile object

Three new integer fields are added to each profile object in the response. They are computed at query time from the `sessions` and `events` tables and are not stored in the profile JSON or the SQLite schema.

| Field | Type | Description |
|---|---|---|
| `session_count` | `int` | Total number of sessions ever started for this profile |
| `total_in` | `int` | Lifetime count of `direction="in"` events across all sessions |
| `total_out` | `int` | Lifetime count of `direction="out"` events across all sessions |

**Computation**:
```sql
SELECT
  s.profile_id,
  COUNT(DISTINCT s.id)                          AS session_count,
  COUNT(CASE WHEN e.direction='in'  THEN 1 END) AS total_in,
  COUNT(CASE WHEN e.direction='out' THEN 1 END) AS total_out
FROM sessions s
LEFT JOIN events e ON e.session_id = s.id
GROUP BY s.profile_id
```

Profiles with no sessions return `session_count=0, total_in=0, total_out=0` (handled by Python default dict, not by the SQL query which only returns rows for profiles that have at least one session).

---

## No New Database Tables or Columns

The SQLite schema (`sessions`, `events`) is unchanged. The session timer on the count page derives from `sessions.started_at`, which already exists. The stats aggregation reads existing `events` rows.

---

## In-Memory State Changes

### CountingService — stop() order

No new fields. The bug fix changes the *execution order* of `stop()`:

```
Before: set _running=False → thread.join(3s) → cap.release()
After:  set _running=False → cap.release() → cap=None → thread.join(5s)
```

The in-memory state after `stop()` is identical to before; only the order of operations changes.

---

## Frontend State Changes

### count.js — session timer

| Variable | Type | Default | Description |
|---|---|---|---|
| `sessionStart` | `Date \| null` | `null` | Set from `session.started_at` in `init()`; drives the timer |
| `timerInterval` | `number \| null` | `null` | `setInterval` handle for the 1-second timer tick; cleared in stop handler |
| `autoRetries` | `number` | `0` | Count of silent stream retries attempted since page load |
| `pageLoadTime` | `number` | `Date.now()` | Page load timestamp; used to enforce the 15-second auto-retry window |

### calibrate.js — video removal

| Variable | Removed? | Notes |
|---|---|---|
| `captureMode` | Removed | Was `"photo"` or `"video"`; always `"photo"` now, hardcoded in save body |

All other calibrate.js state variables are unchanged.
