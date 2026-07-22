"""Recorder: the entry point for capturing backend traffic."""
from __future__ import annotations

import time
from typing import Any, List, Optional

from ..exceptions import RecorderStateError
from ..storage.base import StorageBackend
from ..storage.jsonl_storage import JSONLStorage
from .._queue import EventQueue
from .models import ReplayEvent, Session, new_id


class Recorder:
    """Records HTTP and SQL traffic into replayable sessions.

    Example
    -------
    >>> from replayio import Recorder
    >>> recorder = Recorder()
    >>> recorder.start(name="checkout-flow")
    >>> # ... application code that makes requests / runs queries ...
    >>> session = recorder.stop()

    Or as a context manager::

        with Recorder(name="checkout-flow") as recorder:
            ...  # application code
        session = recorder.session  # populated after the block exits
    """

    def __init__(
        self,
        storage: Optional[StorageBackend] = None,
        name: str = "session",
        http: bool = True,
        httpx: bool = False,
        sqlalchemy_engine: Optional[Any] = None,
        batch_size: int = 100,
        flush_interval: float = 1.0,
    ):
        self.storage: StorageBackend = storage or JSONLStorage()
        self._default_name = name
        self._http_enabled = http
        self._httpx_enabled = httpx
        self._sqlalchemy_engine = sqlalchemy_engine
        self._batch_size = batch_size
        self._flush_interval = flush_interval

        self.session: Optional[Session] = None
        self._queue: Optional[EventQueue] = None
        self._adapters: List[Any] = []
        self._last_stopped_session: Optional[Session] = None

    def start(self, name: Optional[str] = None) -> Session:
        if self.session is not None:
            raise RecorderStateError("Recorder already started; call stop() first")

        self.session = Session(
            id=new_id(), name=name or self._default_name, started_at=time.time()
        )
        self.storage.save_session(self.session)

        self._queue = EventQueue(self.storage, self._batch_size, self._flush_interval)
        self._queue.start()

        self._adapters = []
        if self._http_enabled:
            from ..adapters.http_adapter import HTTPAdapter

            self._install(HTTPAdapter(self))
        if self._httpx_enabled:
            from ..adapters.httpx_adapter import HTTPXAdapter

            self._install(HTTPXAdapter(self))
        if self._sqlalchemy_engine is not None:
            from ..adapters.sqlalchemy_adapter import SQLAlchemyAdapter

            self._install(SQLAlchemyAdapter(self, self._sqlalchemy_engine))

        return self.session

    def _install(self, adapter) -> None:
        adapter.patch()
        self._adapters.append(adapter)

    def record_event(self, event: ReplayEvent) -> None:
        """Called by adapters for every captured interaction."""
        if self._queue is None or self.session is None:
            return
        self._queue.put(event)
        self.session.event_count += 1

    def stop(self) -> Session:
        if self.session is None:
            raise RecorderStateError("Recorder not started")

        for adapter in self._adapters:
            adapter.unpatch()
        self._adapters = []

        assert self._queue is not None
        self._queue.stop()
        self._queue = None

        self.session.ended_at = time.time()
        self.storage.update_session(self.session)

        finished = self.session
        self._last_stopped_session = finished
        self.session = None
        return finished

    @property
    def last_session(self) -> Optional[Session]:
        """The most recently completed session, populated after stop() runs
        (including via the context-manager __exit__)."""
        return self._last_stopped_session

    def __enter__(self) -> "Recorder":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.stop()
        return False
