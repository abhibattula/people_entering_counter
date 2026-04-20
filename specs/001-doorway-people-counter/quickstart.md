# Quickstart: Doorway People Counter

**Phase**: 1 — Design & Contracts
**Date**: 2026-04-20

---

## Prerequisites

- Python 3.10 or later
- pip
- A webcam (built-in or USB)
- Modern Chromium or Firefox browser

---

## Installation

```bash
# Clone or download the project
cd doorway-counter

# Install Python dependencies
pip install -r requirements.txt
```

`requirements.txt`:
```
fastapi
uvicorn[standard]
ultralytics
opencv-python
aiofiles
python-multipart
pytest
httpx
pytest-asyncio
```

> **Note**: `ultralytics` will download YOLOv8n weights (~6MB) on first run.

---

## Running the System

```bash
python run.py
```

Then open **http://localhost:8000** in your browser.

That's it — one command, no build step.

---

## First-Time Setup (Calibration)

1. Click **"Create New Door/Entryway Profile"** on the home screen.
2. Allow camera access when the browser asks.
3. Aim the camera so the doorway fills 20–60% of the frame.
4. Choose **5-photo guided capture** (recommended) or **5-second video clip**.
5. Follow the on-screen position instructions (photo mode) or wait for the countdown (video mode).
6. Review the placement quality indicators. Re-capture if needed.
7. Confirm the proposed doorway outline and inside direction.
8. Give the profile a name and save it.
9. Live counting begins automatically.

---

## Daily Use (Returning User)

1. Open **http://localhost:8000**.
2. Click a saved profile name.
3. Counting starts immediately — IN, OUT, and OCCUPANCY displayed live.
4. Click **Export CSV** to download the session log.
5. Click **Stop** when done.

---

## Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# With coverage
pytest --cov=backend tests/
```

---

## Project Layout (quick reference)

```
backend/    Python FastAPI server
frontend/   Plain HTML + JS + CSS (served by FastAPI)
data/       SQLite database (gitignored)
tests/      pytest suite
run.py      Start the server
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| "Camera unavailable" error | Close other apps using the camera (Zoom, Teams, etc.) |
| Stream doesn't load | Check http://localhost:8000/api/health — camera_available must be true |
| Doorway not detected | Re-capture ensuring the door is fully visible and well-lit |
| Counts seem wrong | Verify the counting line is centred in the doorway and inside direction is correct |
| Port 8000 in use | Edit `run.py` and change `port=8000` to another port |
