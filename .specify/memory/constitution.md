<!-- Sync Impact Report
Version change: DRAFT → 1.0.0 (initial ratification)
Added sections: Core Principles (I–V), Technical Constraints, Development Workflow, Governance
Templates requiring updates:
  ✅ .specify/templates/plan-template.md — Constitution Check gates derived from principles below
  ✅ .specify/templates/spec-template.md — Scope/requirements aligned with Local-Only and Spec-First principles
  ✅ .specify/templates/tasks-template.md — Task categorization reflects TDD, camera handoff, and observability requirements
Follow-up TODOs: none — all sections fully defined for v1.0.0
-->

# Doorway People Counter Constitution

## Core Principles

### I. Spec-First (NON-NEGOTIABLE)
Every feature, change, or fix MUST have an approved spec entry before any code is written.
The canonical spec lives at `docs/superpowers/specs/2026-04-20-doorway-people-counter-design.md`.
No implementation may contradict the spec. If the spec needs updating, amend it first, then code.
API contracts, data models, and UI flows defined in the spec are binding — deviations require an explicit spec amendment with rationale.

### II. Local-Only, Zero Cloud
All user data — door profiles (JSON) and count history (SQLite) — MUST remain on the local machine.
No count events, frames, or profile data may be transmitted to any external service.
ML inference (YOLOv8) MUST run locally via the Python backend. No cloud inference APIs permitted.
`backend/profiles/` and `data/` MUST be listed in `.gitignore` at all times.

### III. Test-First (NON-NEGOTIABLE)
TDD is mandatory: tests are written and confirmed to fail before implementation begins.
Red-Green-Refactor cycle is strictly enforced for every service function and API route.
Unit tests cover: calibration_service, counting_service, quality_service, model_service, database layer.
Integration tests cover: full calibration POST → profile save flow, WebSocket count event emission, MJPEG stream delivery.
No PR or task may be marked complete unless all tests pass.

### IV. Single Camera Ownership
Only one process may hold the camera at any time.
During calibration: the browser owns it via `getUserMedia()`.
During live counting: Python/OpenCV owns it exclusively.
The handoff is explicit: browser MUST call `stream.getTracks().forEach(t => t.stop())` before the counting route loads.
Any code that opens `cv2.VideoCapture` MUST close it before returning control to the browser.
Concurrent camera access is a hard violation — no exceptions.

### V. Minimal Stack, No Build Step
Frontend MUST be plain HTML + vanilla JS + one CSS file. No React, Vue, bundlers, transpilers, or npm dependencies.
Backend MUST use only: `fastapi`, `uvicorn`, `ultralytics`, `opencv-python`, `aiofiles` (plus their transitive deps).
The system MUST start with a single command: `python run.py`.
No ORMs — SQLite accessed via the standard `sqlite3` module directly.
Adding a new dependency requires explicit justification in the spec amendment.

## Technical Constraints

**Runtime**: Python 3.10+ | Browser: modern Chromium/Firefox (no IE, no polyfills)
**ML Model**: YOLOv8n (nano variant) — fastest, lowest memory footprint; upgrade to YOLOv8s only with benchmarked justification
**Tracker**: ByteTrack (built into Ultralytics) — no external tracking library
**Video delivery**: MJPEG over HTTP (`multipart/x-mixed-replace`) for the live stream; no WebRTC, no HLS
**Count events**: WebSocket (`/ws/counts`) — one JSON message per crossing event
**Performance floor**: Inference pipeline MUST maintain ≥10 fps on a mid-range laptop CPU; warning badge shown if fps drops below threshold
**Frame coverage**: Doorway MUST occupy 20–60% of the camera frame for reliable detection; quality check enforces this
**Storage limits**: SQLite events table has no hard cap but Export CSV is offered when disk usage exceeds 500 MB
**Camera index**: Default 0; selectable via `/api/cameras` if default fails

## Development Workflow

**Branch naming**: `{###}-{feature-name}` using sequential numbering (e.g., `001-project-setup`, `002-calibration-backend`)
**Spec → Plan → Tasks → Implement**: All work flows through speckit commands in this order; no skipping steps
**Camera handoff testing**: Every PR touching calibration or counting routes MUST include a manual verification that camera releases cleanly between phases (automated where possible, documented where not)
**Gitignore gate**: CI (or pre-commit check) MUST verify `backend/profiles/` and `data/` are gitignored before merge
**Commit message format**: `type(scope): description` — types: feat, fix, test, docs, refactor, chore
**No half-finished implementations**: Every merged task MUST be functional end-to-end; no feature flags, no dead code paths

## Governance

This constitution supersedes all other practices, conventions, and preferences.
Amendments require: (1) update the design spec, (2) update this constitution, (3) update affected templates, (4) commit all three atomically.
Compliance is reviewed at the start of every `/speckit-plan` and `/speckit-implement` session via the Constitution Check gate.
Principles I (Spec-First) and III (Test-First) and IV (Single Camera Ownership) are non-negotiable — they may not be suspended for expedience.
Complexity exceptions (e.g., adding a dependency) require a written justification entry in the plan's Complexity Tracking table.
Runtime development guidance: see `CLAUDE.md` for agent-specific instructions.

**Version**: 1.0.0 | **Ratified**: 2026-04-20 | **Last Amended**: 2026-04-20
