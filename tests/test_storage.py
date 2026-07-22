import pytest

from replayio.core.models import ReplayEvent, Session, new_id
from replayio.storage.jsonl_storage import JSONLStorage
from replayio.storage.sqlite_storage import SQLiteStorage
from replayio.exceptions import SessionNotFoundError


def _make_session() -> Session:
    import time

    return Session(id=new_id(), name="s", started_at=time.time())


def _make_event(session_id: str) -> ReplayEvent:
    return ReplayEvent(
        id=new_id(), session_id=session_id, adapter="http", operation="GET",
        request={"url": "http://x"}, response={"status_code": 200},
        duration_ms=1.0, status="success",
    )


@pytest.mark.parametrize("backend_factory", [
    lambda tmp_path: JSONLStorage(root=str(tmp_path / "sessions")),
    lambda tmp_path: SQLiteStorage(path=str(tmp_path / "rk.db")),
])
def test_save_and_read_roundtrip(tmp_path, backend_factory):
    storage = backend_factory(tmp_path)
    session = _make_session()
    storage.save_session(session)

    events = [_make_event(session.id) for _ in range(5)]
    storage.save_events(events)

    session.event_count = 5
    session.ended_at = session.started_at + 1
    storage.update_session(session)

    fetched = storage.get_session(session.id)
    assert fetched.event_count == 5
    assert fetched.ended_at is not None

    stored_events = list(storage.iter_events(session.id))
    assert len(stored_events) == 5
    assert all(e.adapter == "http" for e in stored_events)


@pytest.mark.parametrize("backend_factory", [
    lambda tmp_path: JSONLStorage(root=str(tmp_path / "sessions")),
    lambda tmp_path: SQLiteStorage(path=str(tmp_path / "rk.db")),
])
def test_missing_session_raises_on_iter(tmp_path, backend_factory):
    storage = backend_factory(tmp_path)
    with pytest.raises(SessionNotFoundError):
        list(storage.iter_events("does-not-exist"))


@pytest.mark.parametrize("backend_factory", [
    lambda tmp_path: JSONLStorage(root=str(tmp_path / "sessions")),
    lambda tmp_path: SQLiteStorage(path=str(tmp_path / "rk.db")),
])
def test_list_and_delete_sessions(tmp_path, backend_factory):
    storage = backend_factory(tmp_path)
    s1, s2 = _make_session(), _make_session()
    storage.save_session(s1)
    storage.save_session(s2)

    sessions = storage.list_sessions()
    assert {s.id for s in sessions} == {s1.id, s2.id}

    storage.delete_session(s1.id)
    remaining = storage.list_sessions()
    assert {s.id for s in remaining} == {s2.id}
