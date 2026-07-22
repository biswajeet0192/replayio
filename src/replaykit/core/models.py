"""Core data models used throughout ReplayKit."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional


def new_id() -> str:
    """Generate a new unique identifier."""
    return uuid.uuid4().hex


@dataclass
class ReplayEvent:
    """A single normalized, replayable backend interaction.

    Every adapter (HTTP, SQL, ...) produces instances of this class so the
    rest of the system (storage, replay, comparison, reporting) never has
    to know which library originally produced the event.
    """

    id: str
    session_id: str
    adapter: str          # e.g. "http", "sql"
    operation: str        # e.g. "GET", "SELECT"
    request: Dict[str, Any]
    response: Dict[str, Any]
    duration_ms: float
    status: str            # "success" | "error"
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReplayEvent":
        return cls(**data)


@dataclass
class Session:
    """Metadata describing one recording session."""

    id: str
    name: str
    started_at: float
    ended_at: Optional[float] = None
    event_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        return cls(**data)
