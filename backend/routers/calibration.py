import io
from typing import List, Annotated

import cv2
import numpy as np
from fastapi import APIRouter, File, Form, UploadFile, HTTPException

from backend.services.calibration_service import CalibrationSession, TooManyRetriesError
from backend.services.quality_service import assess_quality

router = APIRouter()

# In-memory session store keyed by a simple cookie/header approach.
# For simplicity (single-user local tool) we keep one global session.
_session = CalibrationSession()


def _get_or_create_session() -> CalibrationSession:
    return _session


def _reset_session() -> None:
    global _session
    _session = CalibrationSession()


async def _read_frames(files: List[UploadFile]) -> List[np.ndarray]:
    frames = []
    for f in files:
        data = await f.read()
        arr = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(422, detail=f"Could not decode image: {f.filename}")
        frames.append(img)
    return frames


def _build_response(quality: dict, proposal: dict) -> dict:
    return {
        "quality_check": quality,
        "proposal": {
            "roi_polygon": proposal["roi_polygon"],
            "counting_line": proposal["counting_line"],
            "inside_direction": proposal["inside_direction"],
            "confidence": proposal["confidence"],
            "best_frame_b64": proposal["best_frame_b64"],
            "manual_fallback_available": proposal.get("manual_fallback_available", False),
        },
    }


@router.post("/calibrate/frames")
async def calibrate_frames(
    frames: Annotated[List[UploadFile], File()],
    mode: Annotated[str, Form()],
):
    if mode not in ("photo", "video"):
        raise HTTPException(422, detail="mode must be 'photo' or 'video'")
    if not frames or len(frames) == 0:
        raise HTTPException(422, detail="At least one frame is required")
    if len(frames) > 15:
        raise HTTPException(422, detail="Maximum 15 frames allowed")

    _reset_session()
    imgs = await _read_frames(frames)
    quality = assess_quality(imgs)
    session = _get_or_create_session()
    proposal = session.propose(imgs, mode)
    return _build_response(quality, proposal)


@router.post("/calibrate/retry")
async def calibrate_retry(
    frames: Annotated[List[UploadFile], File()],
    mode: Annotated[str, Form()],
):
    if mode not in ("photo", "video"):
        raise HTTPException(422, detail="mode must be 'photo' or 'video'")
    if not frames or len(frames) == 0:
        raise HTTPException(422, detail="At least one frame is required")

    imgs = await _read_frames(frames)
    quality = assess_quality(imgs)
    session = _get_or_create_session()
    try:
        proposal = session.propose(imgs, mode)
    except TooManyRetriesError:
        raise HTTPException(429, detail="Maximum retries exceeded")
    return _build_response(quality, proposal)
