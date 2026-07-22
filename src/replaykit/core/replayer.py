"""Replayer: re-executes recorded events against live systems."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, List, Optional

from ..exceptions import SessionNotFoundError
from ..storage.base import StorageBackend
from .comparator import compare
from .models import ReplayEvent, new_id


@dataclass
class ReplayResult:
    original: ReplayEvent
    replay: Optional[ReplayEvent]
    comparison: dict


class Replayer:
    """Reads a recorded session back and re-executes its events.

    HTTP events are replayed by re-issuing the exact request. SQL events
    are replayed only when they are read-only (SELECT) by default, since
    blindly re-running INSERT/UPDATE/DELETE against a live database is
    rarely what you want during debugging - pass ``allow_mutations=True``
    to opt in explicitly.
    """

    def __init__(
        self,
        storage: StorageBackend,
        sqlalchemy_engine: Optional[Any] = None,
        allow_mutations: bool = False,
    ):
        self.storage = storage
        self._sqlalchemy_engine = sqlalchemy_engine
        self._allow_mutations = allow_mutations

    def run(
        self, session_id: str, http: bool = True, sql: bool = True
    ) -> List[ReplayResult]:
        session = self.storage.get_session(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)

        results: List[ReplayResult] = []
        for original in self.storage.iter_events(session_id):
            replay_event: Optional[ReplayEvent] = None

            if original.adapter == "http" and http:
                replay_event = self._replay_http(original)
            elif original.adapter == "sql" and sql and self._sqlalchemy_engine is not None:
                replay_event = self._replay_sql(original)
            else:
                continue

            comparison = compare(original, replay_event)
            results.append(ReplayResult(original=original, replay=replay_event, comparison=comparison))

        return results

    def _replay_http(self, original: ReplayEvent) -> Optional[ReplayEvent]:
        import requests

        req = original.request
        method = req.get("method", "GET")
        url = req.get("url")
        if not url:
            return None

        json_body = req.get("body") if isinstance(req.get("body"), (dict, list)) else None
        start = time.perf_counter()
        try:
            response = requests.request(
                method,
                url,
                headers=req.get("headers") or None,
                params=req.get("params") or None,
                json=json_body,
            )
            duration_ms = (time.perf_counter() - start) * 1000
            return ReplayEvent(
                id=new_id(),
                session_id=original.session_id,
                adapter="http",
                operation=original.operation,
                request=req,
                response={
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response.text[:20000],
                },
                duration_ms=round(duration_ms, 3),
                status="success" if response.ok else "error",
                metadata={"replay_of": original.id},
            )
        except Exception as exc:  # noqa: BLE001
            duration_ms = (time.perf_counter() - start) * 1000
            return ReplayEvent(
                id=new_id(),
                session_id=original.session_id,
                adapter="http",
                operation=original.operation,
                request=req,
                response={"error": str(exc)},
                duration_ms=round(duration_ms, 3),
                status="error",
                metadata={"replay_of": original.id},
            )

    def _replay_sql(self, original: ReplayEvent) -> Optional[ReplayEvent]:
        from sqlalchemy import text

        query = original.request.get("query", "")
        is_mutation = not query.strip().upper().startswith("SELECT")
        if is_mutation and not self._allow_mutations:
            return None

        start = time.perf_counter()
        try:
            with self._sqlalchemy_engine.connect() as conn:
                result = conn.execute(text(query))
                if not is_mutation:
                    rows = result.fetchall()
                    row_count = len(rows)
                else:
                    row_count = result.rowcount
                    conn.commit()
            duration_ms = (time.perf_counter() - start) * 1000
            return ReplayEvent(
                id=new_id(),
                session_id=original.session_id,
                adapter="sql",
                operation=original.operation,
                request=original.request,
                response={"row_count": row_count},
                duration_ms=round(duration_ms, 3),
                status="success",
                metadata={"replay_of": original.id},
            )
        except Exception as exc:  # noqa: BLE001
            duration_ms = (time.perf_counter() - start) * 1000
            return ReplayEvent(
                id=new_id(),
                session_id=original.session_id,
                adapter="sql",
                operation=original.operation,
                request=original.request,
                response={"error": str(exc)},
                duration_ms=round(duration_ms, 3),
                status="error",
                metadata={"replay_of": original.id},
            )
