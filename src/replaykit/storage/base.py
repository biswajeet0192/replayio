"""Storage backend interface.

ReplayKit never talks to a concrete storage technology directly - every
component (Recorder, Replayer, CLI, reporting) depends only on this
interface. New backends (PostgreSQL, S3, ...) can be added by implementing
this class without touching any other part of the system.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, List, Optional

from ..core.models import ReplayEvent, Session


class StorageBackend(ABC):
    """Abstract persistence layer for sessions and events."""

    @abstractmethod
    def save_session(self, session: Session) -> None:
        """Persist a newly created session."""

    @abstractmethod
    def update_session(self, session: Session) -> None:
        """Persist updates to an existing session (e.g. on stop())."""

    @abstractmethod
    def save_event(self, event: ReplayEvent) -> None:
        """Persist a single event."""

    def save_events(self, events: List[ReplayEvent]) -> None:
        """Persist a batch of events. Default implementation loops over
        save_event(); backends should override this for better throughput.
        """
        for event in events:
            self.save_event(event)

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[Session]:
        """Return a session by id, or None if it does not exist."""

    @abstractmethod
    def iter_events(self, session_id: str) -> Iterable[ReplayEvent]:
        """Yield every event recorded for a session, in recorded order."""

    @abstractmethod
    def list_sessions(self) -> List[Session]:
        """Return all known sessions, most recent first."""

    @abstractmethod
    def delete_session(self, session_id: str) -> None:
        """Delete a session and all of its events."""

    def close(self) -> None:
        """Release any underlying resources. Optional to override."""
        return None
