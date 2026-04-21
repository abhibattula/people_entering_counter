# Feature Specification: Detection Accuracy & Visual Clarity Fixes

**Feature Branch**: `002-fix-detection-visibility`
**Created**: 2026-04-21
**Status**: Draft
**Input**: Fix 8 confirmed bugs in the doorway people counter and improve visual output: camera resolution mismatch, tracking ID gate blocking detection, missing YOLO heatmap in door detection, arbitrary polygon corner selection, wrong inside-direction inference, broken manual draw canvas, FPS divide-by-zero, permissive door visibility check. Add grayscale mode, prominent door box overlay, thicker counting line with label, and always-visible people boxes.

---

## User Scenarios & Testing

### User Story 1 — People Are Detected and Shown Immediately (Priority: P1)

A user starts a live counting session. They expect to see green bounding boxes around every person visible in the doorway area as soon as they appear — not just after a delay or only when the person moves.

**Why this priority**: This is the core value of the system. If people are not detected and shown, every other feature is irrelevant. The current resolution mismatch bug means people are never inside the ROI, so the system appears completely broken on first use.

**Independent Test**: A user opens an existing profile and stands in front of the camera. Green bounding boxes appear around them within one second, regardless of whether they are moving or standing still.

**Acceptance Scenarios**:

1. **Given** a profile was calibrated at any camera resolution, **When** the live counting view loads, **Then** people are detected and green boxes drawn on the live stream at the same scale as the captured doorway boundary.
2. **Given** a person stands completely still in front of the camera, **When** 3 seconds have passed, **Then** a green bounding box remains on that person (no box disappearing because the tracker lost a static person's ID).
3. **Given** two people are in the doorway simultaneously, **When** the stream renders the frame, **Then** both receive their own bounding box with a visible ID label.

---

### User Story 2 — Door Boundary Is Accurately Proposed and Clearly Shown (Priority: P1)

A user goes through the calibration wizard. They expect the system to correctly identify where the door is in the frame and draw a clearly labelled boundary box around it — even if the camera is not perfectly still.

**Why this priority**: If the door boundary is wrong, the counting line is wrong, and every count event is wrong. This is the second most critical issue after people detection.

**Independent Test**: A user runs calibration in a standard doorway (20–60% of frame). The proposed ROI polygon visibly surrounds the door frame, not a wall or piece of furniture. The "DOOR" label and boundary are visible on the live stream.

**Acceptance Scenarios**:

1. **Given** captured calibration frames show people walking through the doorway, **When** the system proposes a door boundary, **Then** the proposal polygon encloses the region where people appeared, not just the largest edge-detected contour.
2. **Given** the system returns a doorway proposal, **When** the proposal is displayed to the user, **Then** a labelled bounding box titled "DOOR" is drawn around the boundary on the preview image.
3. **Given** the live counting view is active, **When** any frame renders, **Then** a purple dashed polygon and a "DOOR" text label are always visible on the stream overlaying the saved door region.
4. **Given** a doorway occupies 30% of the camera frame, **When** calibration runs, **Then** the system proposes a polygon with 4 well-chosen corners (not arbitrarily selected from a larger set), correctly ordered top-left → top-right → bottom-right → bottom-left.

---

### User Story 3 — Inside/Outside Direction Is Correct (Priority: P1)

A user confirms the doorway boundary and the system shows a green arrow indicating which side is "inside." The arrow must point in the right direction for IN and OUT counts to be correct.

**Why this priority**: A wrong direction means every IN is counted as OUT and vice versa. The count is worse than useless — it is actively misleading.

**Independent Test**: A user walks from outside to inside through the door. The IN counter increments. The direction arrow shown on the proposal screen matches the direction of "inside" as confirmed by the user.

**Acceptance Scenarios**:

1. **Given** the system proposes a direction, **When** the user is presented with the direction arrow, **Then** they can accept it or explicitly flip it before saving, and the saved direction matches their choice.
2. **Given** the user confirms the profile with inside direction "up," **When** someone walks in the direction that crosses the line from below to above, **Then** the IN counter increments.

---

### User Story 4 — Manual Door Drawing Works with Clear Visual Feedback (Priority: P2)

A user who rejects the auto-proposal switches to manual draw mode. They click 4 corners on the image. Each click shows an immediately visible coloured marker with a counter ("1/4", "2/4" …). After the 4th click the boundary polygon and counting line appear, and "Save" becomes enabled.

**Why this priority**: When auto-detection fails, manual draw is the only fallback. If it appears to not respond to clicks, the user is stuck with no way to proceed.

**Independent Test**: A user in manual draw mode clicks 4 points anywhere on the canvas. Four numbered markers appear at each click position. After the 4th click a polygon and counting line are drawn and the Save button activates.

**Acceptance Scenarios**:

1. **Given** the manual draw step is shown, **When** the user clicks anywhere on the canvas, **Then** a numbered circle marker (e.g., "1", "2", "3", "4") appears at exactly the clicked position — visible against both light and dark backgrounds.
2. **Given** 4 points have been placed, **When** the canvas re-renders, **Then** the background doorway image is still fully visible underneath the polygon and markers.
3. **Given** the user clicks "Reset", **When** the canvas redraws, **Then** the background image is restored and all previously placed markers are removed.
4. **Given** the polygon is saved from manual draw, **When** the profile is used for counting, **Then** the counting line lies within the saved polygon boundary.

---

### User Story 5 — Counting Line Is Clearly Visible on the Live Stream (Priority: P2)

A user watching the live counting view can immediately identify where the virtual counting line is — it stands out clearly from the video content, has a label ("COUNT LINE" or similar), and is thick enough to see at a glance.

**Why this priority**: Users need to understand what the camera is "watching for." A faint yellow line is invisible on many backgrounds. Clear labelling builds trust that the system is working.

**Independent Test**: A user opens the live counting view and immediately identifies the counting line within 3 seconds without any instructions or explanation.

**Acceptance Scenarios**:

1. **Given** the live stream is running, **When** any frame renders, **Then** the counting line is drawn at thickness ≥ 3px and has a text label ("COUNT LINE") positioned near the line midpoint.
2. **Given** the live stream is running, **When** any frame renders, **Then** the direction arrow is drawn in a contrasting colour (green) with an arrowhead visible at the "inside" end.

---

### User Story 6 — Grayscale Mode Reduces System Load (Priority: P3)

A user on a low-spec laptop can enable grayscale mode from the counting view. The stream switches to black-and-white frames, reducing the data transmitted and processed per frame.

**Why this priority**: Grayscale reduces per-frame memory and bandwidth by roughly one-third and allows the system to maintain ≥10 fps on machines with limited resources. It is a quality-of-life option, not a critical fix.

**Independent Test**: A user enables grayscale mode. The live stream immediately shows black-and-white frames. The people detection and counting line overlays remain visible. FPS improves or is maintained.

**Acceptance Scenarios**:

1. **Given** the live counting view is active, **When** the user toggles "Grayscale mode", **Then** the live stream switches to black-and-white within 2 seconds without restarting the session.
2. **Given** grayscale mode is active, **When** a person crosses the counting line, **Then** the IN/OUT counter still increments correctly.
3. **Given** grayscale mode is active, **When** the overlays render, **Then** the door boundary, counting line, direction arrow, and person bounding boxes are all still clearly visible (using white/yellow/green overlays on the grayscale image).

---

### User Story 7 — System Remains Stable Under All Frame Conditions (Priority: P2)

The counting service background thread must not crash silently. If a frame rate anomaly occurs or the camera feeds extremely fast frames, the system must not freeze or produce an unhandled error.

**Why this priority**: A frozen stream with no error message leaves the user unable to diagnose the problem. Stability is a basic reliability requirement.

**Independent Test**: The live stream runs for 10 minutes without freezing, even if frames arrive at an uneven rate or in rapid bursts.

**Acceptance Scenarios**:

1. **Given** the camera delivers frames at an irregular rate, **When** the FPS counter is calculated, **Then** the system does not crash and instead shows "0.0 fps" or the last valid reading.
2. **Given** the counting service is running, **When** an unexpected internal error occurs in the background thread, **Then** the error is logged and the stream stops cleanly rather than freezing silently.

---

### Edge Cases

- What if the camera resolution at calibration and at live counting are different? → The system must scale ROI coordinates to match the actual live frame resolution.
- What if ByteTrack does not assign IDs for the first N frames? → People must still be drawn as detected (without a crossing-check) until IDs are assigned.
- What if all captured calibration frames contain no visible people? → Door detection must still attempt a boundary using edge analysis, and the quality check must warn that crowding-risk assessment could not run.
- What if the user places manual draw points very close together forming a degenerate polygon? → The system should warn that the polygon is too small and prevent saving.
- What if grayscale mode is toggled while someone is mid-crossing? → The current frame's crossing detection must complete before the colour conversion applies.
- What if the door visibility quality check runs on a plain white wall with no door? → The check must return "door not fully visible" rather than passing based on edge noise alone.

---

## Requirements

### Functional Requirements

- **FR-001**: The system MUST set the live camera capture resolution to match the resolution stored in the door profile before beginning the counting loop.
- **FR-002**: The system MUST draw detected people bounding boxes on every frame where YOLO detects a person inside the doorway ROI, regardless of whether ByteTrack has assigned a tracking ID.
- **FR-003**: The system MUST only record a line-crossing event for people that have an assigned tracking ID and a known previous centroid position.
- **FR-004**: The calibration system MUST use YOLO person-detection results across all captured frames to build a person-density corridor, and MUST intersect this corridor with edge-detected contours to propose the door boundary.
- **FR-005**: When selecting a 4-point polygon from a detected contour, the system MUST use the 4 geometrically most significant corners (not the first 4 points in the array), ordered top-left → top-right → bottom-right → bottom-left.
- **FR-006**: The manual draw canvas MUST redraw the background image and all placed markers on every click, so the canvas state is always consistent.
- **FR-007**: Each placed manual draw marker MUST be rendered as a numbered circle (showing "1", "2", "3", or "4") with a contrasting white outline, large enough to be clearly visible on a real-world camera image.
- **FR-008**: A progress label (e.g., "Tap corner 2 of 4") MUST be displayed and updated above the manual draw canvas after each click.
- **FR-009**: The system MUST protect the FPS calculation from a zero-duration window; if all buffered frame timestamps are identical, the system MUST return 0.0 without error.
- **FR-010**: The door visibility quality check MUST require both significant edge coverage AND a detectable rectangular structure (reaching at least 2 frame edges), not edge pixel count alone.
- **FR-011**: The live stream MUST draw a "DOOR" text label adjacent to the door boundary polygon on every frame.
- **FR-012**: The counting line MUST be drawn at a minimum thickness of 3 pixels with a "COUNT LINE" text label positioned at the line midpoint.
- **FR-013**: The system MUST offer a grayscale mode toggle that converts frames to black-and-white before JPEG encoding, while keeping all overlay annotations visible in contrasting colours.
- **FR-014**: The inside direction used at profile save time MUST be the direction explicitly confirmed by the user in the calibration wizard, not an inferred default based on ROI screen position.

### Key Entities

- **Door Profile**: Updated to record the user-confirmed inside direction (not the inferred one), and the frame resolution at calibration time which is applied to the live camera on session start.
- **Counting Frame**: Each rendered frame now carries: door boundary polygon with label, counting line with label and direction arrow, person bounding boxes (always drawn when detected), and optional grayscale conversion.
- **Calibration Proposal**: Now derived from the intersection of a YOLO person-density corridor with an edge-detected door contour, giving a boundary grounded in where people actually walked.

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: A person standing still in front of the camera is shown with a bounding box within 1 second of the live view loading, and the box persists while they remain still.
- **SC-002**: After calibration in a standard doorway environment, the proposed door boundary encloses the door frame (not a wall or other object) in at least 90% of test runs with a person visible in the calibration frames.
- **SC-003**: A user in manual draw mode places all 4 corner markers and saves the boundary in under 60 seconds, with clear numbered feedback at each step.
- **SC-004**: The counting line and door boundary label are visible and readable by a new user without instructions within 5 seconds of opening the live counting view.
- **SC-005**: The live stream runs continuously for 10 minutes without the background thread crashing or the stream freezing, under normal and irregular frame-rate conditions.
- **SC-006**: Grayscale mode reduces the per-frame JPEG payload size by at least 20% compared to colour mode, while maintaining ≥10 fps counting throughput.
- **SC-007**: IN and OUT counts are correct (not swapped) for 100% of profiles where the user explicitly confirmed the inside direction in the wizard.

---

## Assumptions

- The door profile JSON schema already stores `frame_width` and `frame_height`; these fields will be used to configure the live camera capture resolution without a schema migration.
- A user-confirmed inside direction will be stored as a new required field `user_confirmed_direction` (falling back to the existing `inside_direction` for profiles created before this fix).
- Grayscale mode is a per-session toggle stored in the browser; it does not persist across sessions or affect stored profiles.
- The YOLO heatmap stage for door detection uses the same `get_model()` singleton already loaded for the quality check — no second model load is needed.
- Manual draw improvements are limited to the canvas interaction and visual feedback; the underlying coordinate system and save logic remain unchanged.
- Existing profiles created before this fix will continue to work; the resolution fix applies only to new sessions started after the fix is deployed.
- The door visibility quality check improvement tightens the threshold but does not change the API response schema.
