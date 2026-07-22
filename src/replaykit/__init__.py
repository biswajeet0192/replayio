"""ReplayKit: record and replay backend traffic (HTTP + SQL) with zero code changes.

Quick start
-----------
    from replayio import Recorder

    recorder = Recorder()
    recorder.start(name="checkout-flow")
    # ... application code ...
    session = recorder.stop()

    from replayio import Replayer, JSONLStorage
    results = Replayer(JSONLStorage()).run(session.id)
"""
from ._version import __version__
from .core.models import ReplayEvent, Session
from .core.recorder import Recorder
from .core.replayer import Replayer, ReplayResult
from .core.comparator import compare
from .storage.base import StorageBackend
from .storage.jsonl_storage import JSONLStorage
from .storage.sqlite_storage import SQLiteStorage
from .reporting import generate_html_report, generate_json_report
from .exceptions import ReplayKitError, SessionNotFoundError, RecorderStateError, StorageError

__all__ = [
    "__version__",
    "Recorder",
    "Replayer",
    "ReplayResult",
    "ReplayEvent",
    "Session",
    "compare",
    "StorageBackend",
    "JSONLStorage",
    "SQLiteStorage",
    "generate_html_report",
    "generate_json_report",
    "ReplayKitError",
    "SessionNotFoundError",
    "RecorderStateError",
    "StorageError",
]
