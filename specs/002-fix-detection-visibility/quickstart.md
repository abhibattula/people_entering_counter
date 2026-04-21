# Quickstart: Detection Accuracy & Visual Clarity Fixes

**Phase**: 1 — Design & Contracts
**Date**: 2026-04-21

This document supplements `specs/001-doorway-people-counter/quickstart.md` with notes specific to this fix release. All setup and installation steps remain unchanged.

---

## What Changed

### People Detection
- People now appear with green bounding boxes immediately — even in the first frame, even when standing still.
- Boxes are slightly dimmer (dark green) when ByteTrack hasn't yet assigned a tracking ID, and full bright green once tracked. Counting only triggers for tracked people.

### Door Boundary
- The calibration wizard now analyses where people appeared in calibration frames to anchor the door boundary proposal. Point the camera at the door, walk through it 1–2 times while photos are taken, and the proposal will be significantly more accurate.
- The live stream now shows a **DOOR** label next to the door boundary polygon.

### Counting Line
- The counting line is thicker (3px) and now shows a **COUNT LINE** label at its midpoint.

### Inside Direction
- In Step 6 of the calibration wizard, a **"Flip direction"** button lets you reverse the arrow if the system guessed wrong. The direction you confirm is the direction that is saved.

### Manual Draw
- Numbered corner markers (1–4) now appear at each click position with high-contrast white outlines.
- A progress label above the canvas shows "Tap corner N of 4" and updates with each click.
- Clicking Reset fully restores the background image.

### Grayscale Mode
- A **"🔲 Grayscale"** toggle button appears in the live counting view.
- Enabling it switches the stream to black-and-white, reducing memory usage and improving frame rate on low-spec machines.
- All overlays (door box, counting line, person boxes) remain visible.

---

## Running Tests

```bash
# All tests (includes new detection and calibration tests)
pytest

# Only the new tests added in this release
pytest tests/unit/test_counting_service.py tests/unit/test_calibration_service.py tests/unit/test_quality_service.py tests/integration/test_stream_grayscale.py -v

# With coverage
pytest --cov=backend tests/
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| People still not detected after upgrade | Check `GET /api/health` — if `camera_available: true`, look at logs for "camera resolution mismatch" warning |
| Door boundary still wrong | Ensure someone walks through the doorway during calibration capture (needed for YOLO heatmap) |
| Direction arrow is backwards | Click "Flip direction" in step 6 before accepting the proposal |
| Grayscale toggle has no effect | Reload the counting page; the toggle reloads the stream URL |
| Manual draw clicks not registering | Wait 1 second after the canvas appears before clicking (image load completes) |
