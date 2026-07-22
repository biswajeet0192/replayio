"""Adapter for SQLAlchemy engines.

Uses SQLAlchemy's `before_cursor_execute` / `after_cursor_execute` engine
events - the same hook points SQLAlchemy itself uses for its own query
logging - so no query builder or ORM code needs to change.
"""
from __future__ import annotations

import json
import time
from typing import Any

from ..core.models import ReplayEvent, new_id
from .base import Adapter

_START_ATTR = "_replaykit_start_time"


class SQLAlchemyAdapter(Adapter):
    name = "sql"

    def __init__(self, recorder: "Any", engine: "Any"):
        self._recorder = recorder
        self._engine = engine
        self._patched = False

    def patch(self) -> None:
        from sqlalchemy import event

        if self._patched:
            return
        event.listen(self._engine, "before_cursor_execute", self._before)
        event.listen(self._engine, "after_cursor_execute", self._after)
        self._patched = True

    def unpatch(self) -> None:
        from sqlalchemy import event

        if not self._patched:
            return
        event.remove(self._engine, "before_cursor_execute", self._before)
        event.remove(self._engine, "after_cursor_execute", self._after)
        self._patched = False

    def _before(self, conn, cursor, statement, parameters, context, executemany) -> None:
        setattr(context, _START_ATTR, time.perf_counter())

    def _after(self, conn, cursor, statement, parameters, context, executemany) -> None:
        start = getattr(context, _START_ATTR, None)
        duration_ms = (time.perf_counter() - start) * 1000 if start is not None else 0.0

        try:
            row_count = cursor.rowcount
        except Exception:  # noqa: BLE001
            row_count = None

        event_obj = ReplayEvent(
            id=new_id(),
            session_id=self._recorder.session.id,
            adapter=self.name,
            operation=_operation_type(statement),
            request={"query": statement, "parameters": _safe_params(parameters)},
            response={"row_count": row_count},
            duration_ms=round(duration_ms, 3),
            status="success",
        )
        self._recorder.record_event(event_obj)


def _operation_type(statement: str) -> str:
    stripped = statement.strip()
    return stripped.split(" ", 1)[0].upper() if stripped else "UNKNOWN"


def _safe_params(parameters: Any) -> Any:
    try:
        json.dumps(parameters)
        return parameters
    except TypeError:
        return str(parameters)
