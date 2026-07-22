"""Filesystem storage backend: one directory per session, JSONL events.

Layout::

    <root>/
        <session_id>/
            metadata.json
            events.jsonl

This backend has zero external dependencies and is the default used when
no storage is configured, matching the v1.0 goal of "extremely lightweight".
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Iterable, List, Optional

from ..core.models import ReplayEvent, Session
from ..exceptions import SessionNotFoundError, StorageError
from .base import StorageBackend


class JSONLStorage(StorageBackend):
    def __init__(self, root: str = ".replayio/sessions"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _session_dir(self, session_id: str) -> Path:
        return self.root / session_id

    def save_session(self, session: Session) -> None:
        session_dir = self._session_dir(session.id)
        session_dir.mkdir(parents=True, exist_ok=True)
        self._write_metadata(session)
        events_path = session_dir / "events.jsonl"
        if not events_path.exists():
            events_path.touch()

    def update_session(self, session: Session) -> None:
        if not self._session_dir(session.id).exists():
            raise SessionNotFoundError(session.id)
        self._write_metadata(session)

    def _write_metadata(self, session: Session) -> None:
        metadata_path = self._session_dir(session.id) / "metadata.json"
        try:
            with self._lock:
                metadata_path.write_text(json.dumps(session.to_dict(), indent=2))
        except OSError as exc:
            raise StorageError(str(exc)) from exc

    def save_event(self, event: ReplayEvent) -> None:
        self.save_events([event])

    def save_events(self, events: List[ReplayEvent]) -> None:
        if not events:
            return
        by_session = {}
        for event in events:
            by_session.setdefault(event.session_id, []).append(event)

        for session_id, session_events in by_session.items():
            session_dir = self._session_dir(session_id)
            session_dir.mkdir(parents=True, exist_ok=True)
            events_path = session_dir / "events.jsonl"
            lines = "\n".join(json.dumps(e.to_dict()) for e in session_events) + "\n"
            with self._lock:
                with events_path.open("a", encoding="utf-8") as fh:
                    fh.write(lines)

    def get_session(self, session_id: str) -> Optional[Session]:
        metadata_path = self._session_dir(session_id) / "metadata.json"
        if not metadata_path.exists():
            return None
        return Session.from_dict(json.loads(metadata_path.read_text()))

    def iter_events(self, session_id: str) -> Iterable[ReplayEvent]:
        events_path = self._session_dir(session_id) / "events.jsonl"
        if not events_path.exists():
            raise SessionNotFoundError(session_id)
        with events_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield ReplayEvent.from_dict(json.loads(line))

    def list_sessions(self) -> List[Session]:
        sessions = []
        for entry in self.root.iterdir():
            metadata_path = entry / "metadata.json"
            if metadata_path.exists():
                sessions.append(Session.from_dict(json.loads(metadata_path.read_text())))
        sessions.sort(key=lambda s: s.started_at, reverse=True)
        return sessions

    def delete_session(self, session_id: str) -> None:
        import shutil

        session_dir = self._session_dir(session_id)
        if session_dir.exists():
            shutil.rmtree(session_dir)
