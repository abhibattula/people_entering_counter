# Data Model: Detection Accuracy & Visual Clarity Fixes

**Phase**: 1 — Design & Contracts
**Date**: 2026-04-21
**Feature**: [spec.md](./spec.md)

---

## Changes to Existing Entities

### Door Profile (profile JSON — no schema migration)

The profile JSON already stores `inside_direction`. No new field is required because the fix ensures the saved `inside_direction` reflects the user's confirmed choice rather than a server-side inference. The profile schema is otherwise **unchanged**.

Existing relevant fields:

| Field | Type | Existing | Change |
|---|---|---|---|
| `inside_direction` | `string` | `"up"` / `"down"` / `"left"` / `"right"` | Now always written from user input, never inferred silently |
| `frame_width` | `int` | Camera capture width in pixels | Now also applied to OpenCV capture on session start |
| `frame_height` | `int` | Camera capture height in pixels | Now also applied to OpenCV capture on session start |

No new top-level fields. No migration script needed. Existing profiles continue to load and run; the resolution fix applies from the next session start.

---

## New Runtime State (in-memory only, not persisted)

### CountingService — new flag

| Field | Type | Default | Description |
|---|---|---|---|
| `_grayscale` | `bool` | `False` | When True, frames are converted to grayscale after overlay rendering before JPEG encode |

This flag is per-service-instance, per-session, set via `svc.set_grayscale(enabled: bool)`. It is not stored in the profile or the database.

### CalibrationService — YOLO heatmap (in-memory during calibration only)

| Field | Type | Description |
|---|---|---|
| `person_mask` | `numpy.ndarray (uint8)` | Accumulated binary occupancy mask built from YOLO detections across all calibration frames. Dimensions match the first captured frame. Discarded after `propose_doorway` returns. |

---

## No New Database Tables or Columns

The SQLite schema (`sessions`, `events`) is unchanged. The grayscale preference is a UI-only session toggle and is not recorded as an event or session attribute.

---

## Validation Rules (unchanged)

All existing validation rules for the Door Profile remain in force:
- `roi_polygon`: exactly 4 `[x, y]` integer pairs
- `counting_line`: `{x1, y1, x2, y2}` integers
- `inside_direction`: one of `"up"`, `"down"`, `"left"`, `"right"`
- `frame_width`, `frame_height`: positive integers ≥ 1
