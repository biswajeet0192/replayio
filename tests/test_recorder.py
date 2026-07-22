import requests

from replayio import Recorder
from replayio.storage.jsonl_storage import JSONLStorage


def test_records_successful_and_failed_requests(live_server, tmp_storage_dir):
    storage = JSONLStorage(root=tmp_storage_dir)
    recorder = Recorder(storage=storage, name="test-session")

    recorder.start()
    requests.get(f"{live_server}/ping")
    requests.post(f"{live_server}/echo", json={"a": 1})
    requests.get(f"{live_server}/fail")
    session = recorder.stop()

    assert session.event_count == 3
    events = list(storage.iter_events(session.id))
    assert len(events) == 3
    assert {e.operation for e in events} == {"GET", "POST"}
    statuses = {e.status for e in events}
    assert statuses == {"success", "error"}


def test_context_manager_usage(live_server, tmp_storage_dir):
    storage = JSONLStorage(root=tmp_storage_dir)
    with Recorder(storage=storage, name="ctx-session") as recorder:
        requests.get(f"{live_server}/ping")

    session = storage.get_session(recorder.last_session.id)
    assert session.event_count == 1


def test_double_start_raises(tmp_storage_dir):
    from replayio.exceptions import RecorderStateError

    storage = JSONLStorage(root=tmp_storage_dir)
    recorder = Recorder(storage=storage)
    recorder.start()
    try:
        import pytest

        with pytest.raises(RecorderStateError):
            recorder.start()
    finally:
        recorder.stop()


def test_stop_without_start_raises(tmp_storage_dir):
    import pytest

    from replayio.exceptions import RecorderStateError

    storage = JSONLStorage(root=tmp_storage_dir)
    recorder = Recorder(storage=storage)
    with pytest.raises(RecorderStateError):
        recorder.stop()
