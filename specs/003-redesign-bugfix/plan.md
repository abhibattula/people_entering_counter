# Implementation Plan: UI Redesign, Bug Fixes & Video Mode Removal

**Branch**: `003-redesign-bugfix` | **Date**: 2026-04-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/003-redesign-bugfix/spec.md`

---

## Summary

Fix three confirmed runtime bugs (camera-release race in `stop()`, Windows camera-handoff hang on navigation, TOCTOU double-open in `stream.py`), remove the video calibration path, redesign all three frontend pages (home, calibration wizard, count view), and enrich `GET /api/profiles` with lifetime totals. All changes are confined to three backend files and five frontend files. No new dependencies, no schema changes.

---

## Technical Context

**Language/Version**: Python 3.10+ (backend) · Vanilla JS/HTML/CSS (frontend)
**Primary Dependencies**: `fastapi`, `uvicorn[standard]`, `ultralytics` (YOLOv8 + ByteTrack), `opencv-python`, `aiofiles` — unchanged
**Storage**: JSON profiles (`backend/profiles/{uuid}.json`) · SQLite (`data/counts.db`) — no migration; three transient fields added to the profiles API response
**Testing**: `pytest` + `httpx` (async) · `pytest-asyncio` — existing suite extended with new unit and integration tests
**Target Platform**: Local laptop (Windows/macOS/Linux) · modern Chromium/Firefox
**Project Type**: Local web-service + browser UI (hybrid desktop app)
**Performance Goals**: ≥10 fps maintained · profiles list loads in <200 ms with stats aggregation
**Constraints**: Fully offline · single command startup · no new dependencies · backward-compatible with existing profiles
**Scale/Scope**: Single user · single active camera · all changes are additive or replace existing logic

---

## Constitution Check

| Principle | Status | Evidence |
|---|---|---|
| I. Spec-First | ✅ PASS | `specs/003-redesign-bugfix/spec.md` exists and is fully populated |
| II. Local-Only, Zero Cloud | ✅ PASS | No new external calls; stats aggregation is a local SQLite query |
| III. Test-First (TDD) | ✅ PASS | Failing tests written before all backend changes; 116/116 tests pass |
| IV. Single Camera Ownership | ✅ PASS | Bug fixes make camera handoff more reliable; no new camera owners added |
| V. Minimal Stack, No Build Step | ✅ PASS | Zero new dependencies; frontend remains vanilla JS |

**Gate result: ALL PASS.**

---

## Project Structure

### Documentation (this feature)

```text
specs/003-redesign-bugfix/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 decisions
├── data-model.md        # Phase 1 data changes
├── quickstart.md        # Phase 1 operational notes
├── contracts/
│   └── api.md           # Phase 1 API delta (GET /api/profiles enriched)
├── checklists/
│   └── requirements.md  # Specification quality gate
└── tasks.md             # Phase 2 task list
```

### Source Code (files changed by this feature)

```text
backend/
├── services/
│   └── counting_service.py    # Bug 1 — swap release/join order in stop()
├── routers/
│   ├── stream.py              # Bug 3 — remove TOCTOU camera pre-check
│   └── profiles.py            # US4 — add total_in/total_out/session_count to list

frontend/
├── js/
│   ├── calibrate.js           # Bug 2a — 1s delay; video removal; named progress bar
│   └── count.js               # Bug 2b — auto-retry; session timer; new DOM refs
├── calibrate.html             # Video removal (step 3 deleted); 8-step named progress bar
├── count.html                 # Header card; tinted count cells; stream badges; bottom panel
├── index.html                 # App header; data-rich profile cards; stats row
└── css/styles.css             # Updated tokens; new component CSS for all redesigned elements

tests/
├── unit/
│   └── test_counting_service.py    # Bug 1 — stop() order test
└── integration/
    └── test_profiles_api.py        # US4 — stats fields in list response
```

---

## Complexity Tracking

No constitution violations. No new dependencies. No complexity exceptions required.
