import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, field_validator

from backend.config import PROFILES_DIR
from backend.services.counting_service import get_or_create_service

router = APIRouter()

_FLIP = {"up": "down", "down": "up", "left": "right", "right": "left"}


# ── Schema ────────────────────────────────────────────────────────────────

class CountingLine(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int


class QualityCheck(BaseModel):
    door_fully_visible: bool
    lighting_acceptable: bool
    crowding_risk: Literal["low", "medium", "high"]
    camera_adjustment: Literal["keep", "closer", "farther"]


class ProfileCreate(BaseModel):
    name: str
    camera_index: int = 0
    capture_mode: Literal["photo", "video"]
    frame_width: int
    frame_height: int
    roi_polygon: list[list[int]]
    counting_line: CountingLine
    inside_direction: Literal["up", "down", "left", "right"]
    door_randomly_opens: bool = False
    quality_check: QualityCheck

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name must not be empty")
        if len(v) > 100:
            raise ValueError("name must be 100 characters or fewer")
        return v

    @field_validator("roi_polygon")
    @classmethod
    def roi_has_four_points(cls, v):
        if len(v) != 4:
            raise ValueError("roi_polygon must have exactly 4 points")
        return v


# ── Helpers ───────────────────────────────────────────────────────────────

def _profile_path(profile_id: str) -> Path:
    return PROFILES_DIR / f"{profile_id}.json"


def _load_profile(profile_id: str) -> dict:
    p = _profile_path(profile_id)
    if not p.exists():
        raise HTTPException(404, detail="Profile not found")
    return json.loads(p.read_text(encoding="utf-8"))


def _save_profile(data: dict) -> None:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    _profile_path(data["id"]).write_text(json.dumps(data, indent=2), encoding="utf-8")


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/profiles")
def list_profiles():
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    profiles = []
    for f in PROFILES_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            profiles.append({"id": data["id"], "name": data["name"], "created_at": data["created_at"]})
        except Exception:
            pass  # skip corrupted files
    profiles.sort(key=lambda p: p["created_at"], reverse=True)
    return profiles


@router.post("/profiles", status_code=201)
def create_profile(body: ProfileCreate):
    profile_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    data = {
        "id": profile_id,
        "created_at": created_at,
        **body.model_dump(),
    }
    _save_profile(data)
    return {"id": profile_id, "created_at": created_at}


@router.get("/profiles/{profile_id}/export")
def export_profile(profile_id: str):
    data = _load_profile(profile_id)
    name = data.get("name", profile_id).replace(" ", "_")
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f'attachment; filename="profile-{name}.json"'},
    )


@router.post("/profiles/import", status_code=201)
async def import_profile(file: UploadFile = File(...)):
    raw = await file.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(422, detail="Invalid JSON")

    required = {"name", "roi_polygon", "counting_line", "inside_direction"}
    if not required.issubset(data.keys()):
        raise HTTPException(422, detail="Missing required profile fields")

    new_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    data["id"] = new_id
    data["created_at"] = created_at
    _save_profile(data)
    return {"id": new_id, "created_at": created_at}


@router.get("/profiles/{profile_id}")
def get_profile(profile_id: str):
    return _load_profile(profile_id)


@router.patch("/profiles/{profile_id}/direction")
def flip_direction(profile_id: str):
    data = _load_profile(profile_id)
    current = data.get("inside_direction", "down")
    new_dir = _FLIP.get(current, "down")
    data["inside_direction"] = new_dir
    _save_profile(data)
    # Update the running service if one exists for this profile
    try:
        svc = get_or_create_service(profile_id)
        if svc.is_running():
            svc.set_direction(new_dir)
    except Exception:
        pass
    return {"inside_direction": new_dir}


@router.delete("/profiles/{profile_id}", status_code=204)
def delete_profile(profile_id: str):
    p = _profile_path(profile_id)
    if not p.exists():
        raise HTTPException(404, detail="Profile not found")
    p.unlink()
    return Response(status_code=204)
