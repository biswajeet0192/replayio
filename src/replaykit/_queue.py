"""Background, batching event queue.

Interceptors never write to storage directly. Instead they push
ReplayEvents onto this in-memory queue, and a single background worker
thread drains it in batches. This keeps recording overhead on the
application's hot path to "append to a queue" (sub-millisecond) instead
of a blocking disk/DB write per event.
"""
from __future__ import annotations

import queue
import threading
from typing import List, Optional

from .core.models import ReplayEvent
from .storage.base import StorageBackend


class EventQueue:
    def __init__(self, storage: StorageBackend, batch_size: int = 100,
                 flush_interval: float = 1.0):
        self._storage = storage
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._q: "queue.Queue[ReplayEvent]" = queue.Queue()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="replayio-writer")
        self._thread.start()

    def put(self, event: ReplayEvent) -> None:
        self._q.put(event)

    def _run(self) -> None:
        batch: List[ReplayEvent] = []
        while True:
            try:
                event = self._q.get(timeout=self._flush_interval)
                batch.append(event)
            except queue.Empty:
                pass

            should_flush = len(batch) >= self._batch_size or (
                batch and self._q.empty()
            )
            if should_flush:
                self._storage.save_events(batch)
                batch = []

            if self._stop_event.is_set() and self._q.empty():
                break

        if batch:
            self._storage.save_events(batch)

    def stop(self, timeout: Optional[float] = 10.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
