"""SQLite storage backend.

Suitable for larger sessions / concurrent readers than the JSONL backend,
while still requiring zero external services. Uses a single shared
connection guarded by a lock, which is sufficient for the write volumes
produced by a recording agent embedded in one process.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from typing import Iterable, List, Optional

from ..core.models import ReplayEvent, Session
from .base import StorageBackend

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    started_at REAL NOT NULL,
    ended_at REAL,
    event_count INTEGER NOT NULL DEFAULT 0,
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    adapter TEXT NOT NULL,
    operation TEXT NOT NULL,
    request TEXT NOT NULL,
    response TEXT NOT NULL,
    duration_ms REAL NOT NULL,
    status TEXT NOT NULL,
    timestamp REAL NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_events_session_id ON events(session_id);
"""


class SQLiteStorage(StorageBackend):
    def __init__(self, path: str = ".replayio/replayio.db"):
        self.path = path
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def save_session(self, session: Session) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO sessions "
                "(id, name, started_at, ended_at, event_count, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    session.id, session.name, session.started_at, session.ended_at,
                    session.event_count, json.dumps(session.metadata),
                ),
            )
            self._conn.commit()

    def update_session(self, session: Session) -> None:
        self.save_session(session)

    def save_event(self, event: ReplayEvent) -> None:
        self.save_events([event])

    def save_events(self, events: List[ReplayEvent]) -> None:
        if not events:
            return
        rows = [
            (
                e.id, e.session_id, e.adapter, e.operation,
                json.dumps(e.request), json.dumps(e.response),
                e.duration_ms, e.status, e.timestamp, json.dumps(e.metadata),
            )
            for e in events
        ]
        with self._lock:
            self._conn.executemany(
                "INSERT OR REPLACE INTO events "
                "(id, session_id, adapter, operation, request, response, "
                "duration_ms, status, timestamp, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            self._conn.commit()

    def get_session(self, session_id: str) -> Optional[Session]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        if row is None:
            return None
        return _row_to_session(row)

    def iter_events(self, session_id: str) -> Iterable[ReplayEvent]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM events WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,),
            ).fetchall()
        for row in rows:
            yield _row_to_event(row)

    def list_sessions(self) -> List[Session]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM sessions ORDER BY started_at DESC"
            ).fetchall()
        return [_row_to_session(row) for row in rows]

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM events WHERE session_id = ?", (session_id,))
            self._conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def _row_to_session(row: sqlite3.Row) -> Session:
    return Session(
        id=row["id"], name=row["name"], started_at=row["started_at"],
        ended_at=row["ended_at"], event_count=row["event_count"],
        metadata=json.loads(row["metadata"]),
    )


def _row_to_event(row: sqlite3.Row) -> ReplayEvent:
    return ReplayEvent(
        id=row["id"], session_id=row["session_id"], adapter=row["adapter"],
        operation=row["operation"], request=json.loads(row["request"]),
        response=json.loads(row["response"]), duration_ms=row["duration_ms"],
        status=row["status"], timestamp=row["timestamp"],
        metadata=json.loads(row["metadata"]),
    )
