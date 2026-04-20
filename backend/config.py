import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

PROFILES_DIR = BASE_DIR / "backend" / "profiles"
DB_PATH = BASE_DIR / "data" / "counts.db"
LOGS_DIR = BASE_DIR / "logs"

MODEL_VARIANT = os.getenv("MODEL_VARIANT", "yolov8n.pt")
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
