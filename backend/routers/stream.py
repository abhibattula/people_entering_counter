import asyncio
import time

import cv2
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from backend.routers.profiles import _load_profile
from backend.services.counting_service import get_or_create_service
from backend.config import CAMERA_INDEX

router = APIRouter()

_BOUNDARY = b"--frame"
_CONTENT_TYPE = b"Content-Type: image/jpeg\r\n\r\n"


async def _mjpeg_generator(profile_id: str, grayscale: bool = False):
    profile = _load_profile(profile_id)
    camera_index = profile.get("camera_index", CAMERA_INDEX)

    svc = get_or_create_service(profile_id)
    if not svc.is_running():
        try:
            svc.start(profile, camera_index)
        except RuntimeError as e:
            raise HTTPException(503, detail=str(e))

    while svc.is_running():
        frame = svc.get_latest_frame()
        if frame:
            yield _BOUNDARY + b"\r\n" + _CONTENT_TYPE + frame + b"\r\n"
        await asyncio.sleep(1 / 30)  # target 30 fps yield rate


@router.get("/stream")
async def mjpeg_stream(profile_id: str, grayscale: bool = False):
    svc = get_or_create_service(profile_id)
    svc.set_grayscale(grayscale)
    return StreamingResponse(
        _mjpeg_generator(profile_id, grayscale=grayscale),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/api/health")
def health():
    from backend.services.model_service import is_model_loaded
    import cv2
    cap = cv2.VideoCapture(CAMERA_INDEX)
    camera_ok = cap.isOpened()
    cap.release()
    return {
        "status": "ok" if (is_model_loaded() and camera_ok) else "degraded",
        "model_loaded": is_model_loaded(),
        "camera_available": camera_ok,
    }


@router.get("/api/cameras")
def list_cameras():
    import cv2
    cameras = []
    for idx in range(5):
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cameras.append({"index": idx, "name": f"Camera {idx}", "resolution": f"{w}x{h}"})
            cap.release()
    return cameras
