import logging
import logging.handlers
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.config import LOGS_DIR, LOG_LEVEL, PROFILES_DIR


@asynccontextmanager
async def lifespan(app: FastAPI):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    handler = logging.handlers.TimedRotatingFileHandler(
        LOGS_DIR / "app.log", when="midnight", backupCount=7, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s — %(message)s"))
    root = logging.getLogger()
    root.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    root.addHandler(handler)

    # Auto-close orphaned sessions from a previous run (FR-021)
    from backend.db.database import get_connection
    conn = get_connection()
    conn.close()
    yield


app = FastAPI(title="Doorway People Counter", lifespan=lifespan)


# ── Routers (registered as they are implemented) ──────────────────────────

from backend.routers import calibration, profiles, sessions, stream, counts  # noqa: E402

app.include_router(calibration.router, prefix="/api")
app.include_router(profiles.router,    prefix="/api")
app.include_router(sessions.router,    prefix="/api")
app.include_router(stream.router)
app.include_router(counts.router)


# ── Static frontend ───────────────────────────────────────────────────────

_frontend = Path(__file__).parent.parent / "frontend"
if _frontend.exists():
    app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")
