# Feature Specification: Doorway People Counter

**Feature Branch**: `001-doorway-people-counter`
**Created**: 2026-04-20
**Status**: Draft
**Input**: User description: "A browser-deployed doorway people counter system using live camera-guided calibration, guided photo/video capture, automatic doorway boundary detection, and real-time IN/OUT counting with profile management per door/entryway."

---

## User Scenarios & Testing

### User Story 1 — First-Time Door Setup (Priority: P1)

A user wants to set up people counting for a doorway. They point their laptop at the door, go through a guided setup, and the system automatically detects the doorway boundary. Once confirmed, live counting begins immediately.

**Why this priority**: This is the entry point for the entire system. Without a working setup flow, nothing else functions. Every other story depends on at least one door profile existing.

**Independent Test**: A new user can open the app, complete the calibration wizard from camera permission through to live counting — with zero manual configuration — and see the IN/OUT counter increment when someone walks through the doorway.

**Acceptance Scenarios**:

1. **Given** no profiles exist, **When** the user clicks "Create New Door/Entryway Profile", **Then** the browser requests camera permission and displays a live preview within 1 second of permission being granted.
2. **Given** the live preview is active, **When** the user selects "5-photo guided capture" and follows the position instructions, **Then** the system collects all 5 photos and proceeds to quality assessment automatically.
3. **Given** captured frames are analysed, **When** the system detects the doorway successfully, **Then** it displays a proposed boundary outline, counting line, and inside/outside direction indicator on the best captured frame.
4. **Given** the doorway proposal is shown, **When** the user confirms "Yes" to both "Is this the door?" and "Is this outline correct?", **Then** the profile is saved and live counting begins without any further user input.
5. **Given** live counting is active, **When** a person walks through the doorway in the "inside" direction, **Then** the IN counter increments by 1 and the OCCUPANCY total updates accordingly.

---

### User Story 2 — Video Clip Capture Mode (Priority: P2)

A user prefers a quicker setup and chooses the 5-second video clip option instead of the guided photo sequence.

**Why this priority**: The video mode is an alternative capture path that trades positional coverage for speed. Users in a hurry or with a stable camera mount benefit from this mode.

**Independent Test**: A user can complete calibration using only the video clip option and arrive at a working people counter without using the photo mode at all.

**Acceptance Scenarios**:

1. **Given** the capture mode selection screen is shown, **When** the user selects "5-second video clip", **Then** a 3-2-1 countdown appears and the clip records for exactly 5 seconds before stopping automatically.
2. **Given** the 5-second clip is recorded, **When** the system processes it, **Then** it extracts 15 evenly-spaced frames and submits them for doorway analysis — identical downstream flow to photo mode.

---

### User Story 3 — Placement Quality Feedback (Priority: P2)

Before committing to a doorway proposal, the user sees clear quality indicators that tell them whether the camera placement is good enough for accurate counting.

**Why this priority**: Poor camera placement is the most common cause of counting errors. Surfacing quality feedback before the profile is saved prevents frustration later.

**Independent Test**: A user with a poorly-placed camera (door cut off, too dark, too close) sees specific, actionable warnings and can re-capture before the profile is saved — without needing to delete and recreate the profile.

**Acceptance Scenarios**:

1. **Given** frames have been captured, **When** the quality assessment runs, **Then** the system displays four indicators: door fully visible (yes/no), lighting acceptable (yes/no), crowding risk (low/medium/high), and camera adjustment recommendation (move closer / move farther / keep current).
2. **Given** the door is not fully visible in the captured frames, **When** the quality check runs, **Then** "Door fully visible: No" is shown and a "Re-capture" button is prominently offered before the user can proceed.
3. **Given** quality warnings are shown, **When** the user clicks "Continue anyway", **Then** the system proceeds to the doorway proposal step without blocking — warnings are advisory, not gates.

---

### User Story 4 — Proposal Rejection and Manual Fallback (Priority: P3)

When the system cannot automatically detect the doorway correctly, the user can correct the boundary manually or trigger a retry.

**Why this priority**: Failure recovery is critical for edge-case environments (unusual door shapes, heavy occlusion, atypical lighting) — but it is not the primary path.

**Independent Test**: A user who rejects the auto-proposal twice can draw the doorway boundary and counting line manually on a canvas, save the profile, and proceed to live counting.

**Acceptance Scenarios**:

1. **Given** a doorway proposal is shown, **When** the user selects "No" to "Is this the door?", **Then** the system retries the automatic proposal analysis (up to 2 retries total).
2. **Given** two automatic proposals have both been rejected, **When** the user sees the third attempt, **Then** a "Draw manually" option becomes available alongside the normal confirmation controls.
3. **Given** the user selects "Draw manually", **When** they drag the polygon handles and reposition the counting line on the canvas, **Then** a "Save this boundary" button allows them to proceed with their custom-drawn region.

---

### User Story 5 — Returning User Loads Existing Profile (Priority: P2)

A returning user opens the app, selects a previously saved door profile, and counting resumes immediately without going through calibration again.

**Why this priority**: The system is meant for repeated daily use. Re-calibrating every session would make it unusable in practice.

**Independent Test**: A user who has already created a profile can open the app, click the profile name, and see the live counting view — counting line and boundary already in place — within 3 seconds.

**Acceptance Scenarios**:

1. **Given** one or more profiles exist, **When** the app home page loads, **Then** all saved profiles are listed with their name and creation date.
2. **Given** the user clicks a profile name, **When** the counting view loads, **Then** the camera activates, the saved boundary and counting line are applied, and counting starts at 0 IN / 0 OUT for the new session.
3. **Given** a session is active, **When** the user clicks "Stop", **Then** the session is saved to history and the camera is released.

---

### User Story 6 — Session Export and History (Priority: P3)

After a counting session, the user can export the event log as a CSV file for use in spreadsheets or reporting tools.

**Why this priority**: Data portability is important for practical use but does not affect the core counting experience.

**Independent Test**: After a completed session, a user can download a CSV file containing a timestamped row for every IN/OUT event recorded during that session.

**Acceptance Scenarios**:

1. **Given** a session has at least one recorded event, **When** the user clicks "Export CSV", **Then** a file downloads containing columns: timestamp, direction (in/out), occupancy at time of event.
2. **Given** multiple sessions exist for a profile, **When** the user views session history, **Then** each session is listed with its start time, end time, total IN, total OUT, and a download link.

---

### Edge Cases

- What happens when camera permission is denied? → Instructions to enable shown; setup cannot proceed until permission is granted.
- What if the camera is already in use by another application? → Error banner shown with retry button; user guided to close conflicting app.
- What if the camera disconnects during live counting? → Counting pauses, reconnection prompt shown, counting resumes automatically when camera returns.
- What if two people cross the counting line simultaneously? → Both crossings are recorded independently using multi-person tracking; neither crossing is missed if the people are not heavily overlapping.
- What if a person stands in the doorway without crossing? → No count recorded; only full crossings from one side to the other are counted.
- What if a person is visible in the background but far from the door? → Not counted; only detections within the doorway boundary region are tracked.
- What if the door opens and closes randomly mid-session? → A readiness warning is shown (if flagged at setup); the system may take up to 60 seconds to adapt before counts are reliable again.
- What if occupancy would go below zero (more OUTs than INs)? → Occupancy is floored at 0; an anomaly is logged for the session.

---

## Requirements

### Functional Requirements

- **FR-001**: The system MUST request camera access via the browser before any setup step proceeds.
- **FR-002**: The system MUST display a live camera preview immediately after permission is granted.
- **FR-003**: The system MUST offer two capture modes: a 5-second video clip and a 5-photo guided sequence.
- **FR-004**: For guided photo capture, the system MUST display a distinct positional instruction for each of the 5 shots and confirm each photo before advancing.
- **FR-005**: The system MUST assess and display four placement quality indicators immediately after capture and before doorway analysis is shown to the user.
- **FR-006**: The system MUST automatically propose a doorway boundary polygon, a counting line, and an inside/outside direction from the captured frames.
- **FR-007**: The system MUST allow the user to confirm or reject the proposed doorway boundary and inside/outside direction independently.
- **FR-008**: The system MUST retry the automatic proposal up to 2 times before unlocking the manual drawing fallback.
- **FR-009**: The system MUST allow the user to manually draw the doorway boundary polygon and counting line on a canvas when automatic proposals fail.
- **FR-010**: The system MUST ask whether the door opens and closes randomly, and display a readiness warning throughout counting if the answer is yes.
- **FR-011**: The system MUST save the confirmed doorway profile (boundary, counting line, direction, quality metadata) to persistent local storage.
- **FR-012**: The system MUST begin live counting immediately after a profile is saved, without requiring the user to restart.
- **FR-013**: The system MUST display IN count, OUT count, and current occupancy (IN minus OUT, minimum 0) prominently during live counting.
- **FR-014**: The system MUST emit a count event for every person who crosses the counting line, recording direction and timestamp.
- **FR-015**: The system MUST track multiple people simultaneously so that concurrent crossings are each recorded independently.
- **FR-016**: The system MUST ignore people detected outside the doorway boundary region.
- **FR-017**: The system MUST display all saved door profiles on the home screen and allow the user to load any profile to resume counting.
- **FR-018**: The system MUST allow the user to export a session's event log as a CSV file.
- **FR-019**: The system MUST allow the user to pause, resume, and stop a counting session.
- **FR-020**: The system MUST release the camera cleanly when the user stops counting or navigates away.

### Key Entities

- **Door Profile**: A named configuration representing one doorway — includes the boundary region, counting line position, inside direction, camera placement metadata, and quality assessment results. Persisted locally. One profile per physical door.
- **Counting Session**: A time-bounded period of active counting against a specific door profile. Has a start time, end time, and a log of all crossing events.
- **Crossing Event**: A single recorded instance of a person crossing the counting line. Has a direction (in/out), a timestamp, and the running occupancy value at the moment of the crossing.
- **Placement Quality Assessment**: A set of four indicators (door visibility, lighting, crowding risk, camera distance recommendation) derived from captured frames before the doorway proposal is shown.

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: A first-time user can complete the full calibration wizard and see their first live count within 3 minutes of opening the app.
- **SC-002**: The system correctly counts IN and OUT crossings with ≥90% accuracy in normal single-person traffic (one person crossing at a time, adequate lighting, door occupying 20–60% of frame).
- **SC-003**: The live view updates the IN/OUT counters within 1 second of a person completing a crossing.
- **SC-004**: A returning user can load an existing profile and begin a new counting session within 5 seconds of opening the app.
- **SC-005**: The system displays actionable quality warnings for at least 3 of the 4 defined placement issues (dark room, door cut off, too close, too far) when those conditions are present.
- **SC-006**: When automatic doorway detection fails, 100% of users are offered a manual drawing fallback without needing to restart the app.
- **SC-007**: A CSV export of a 100-event session downloads and opens correctly in a spreadsheet application within 3 seconds.
- **SC-008**: The system maintains ≥10 frames per second during live counting on a mid-range laptop.

---

## Assumptions

- Users are operating on a laptop with a built-in or USB webcam accessible to the browser.
- The system runs locally on a single machine — no multi-user or networked deployment is in scope for v1.
- A single camera and a single active door profile are used at a time; simultaneous multi-door counting is out of scope.
- The doorway must occupy between 20% and 60% of the camera frame for reliable automatic detection; extreme distances or angles are not supported.
- Users have Python 3.10 or later installed and can run a local server via a single terminal command.
- The browser used supports `getUserMedia()` and `MediaRecorder` (modern Chromium or Firefox).
- Cloud connectivity is not required; all processing and storage is local.
- Retraining or fine-tuning the detection model is out of scope; the system uses a pre-trained model with region-of-interest filtering.
- Mobile browser support is out of scope for v1.
