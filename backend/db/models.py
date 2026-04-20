from dataclasses import dataclass
from typing import Optional


@dataclass
class Session:
    id: str
    profile_id: str
    started_at: str
    ended_at: Optional[str] = None


@dataclass
class CrossingEvent:
    id: int
    session_id: str
    profile_id: str
    timestamp: str
    direction: str  # "in" | "out"
    occupancy: int
