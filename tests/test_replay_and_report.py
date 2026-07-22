import requests

from replayio import Recorder, Replayer, generate_html_report, generate_json_report
from replayio.storage.jsonl_storage import JSONLStorage


def test_replay_matches_original(live_server, tmp_storage_dir):
    storage = JSONLStorage(root=tmp_storage_dir)
    recorder = Recorder(storage=storage, name="replay-session")
    recorder.start()
    requests.get(f"{live_server}/ping")
    session = recorder.stop()

    results = Replayer(storage).run(session.id)
    assert len(results) == 1
    assert results[0].comparison["status_match"] is True
    assert results[0].comparison["diff"]["status_code_match"] is True


def test_replay_detects_mismatch_after_endpoint_change(live_server, tmp_storage_dir):
    storage = JSONLStorage(root=tmp_storage_dir)
    recorder = Recorder(storage=storage, name="mismatch-session")
    recorder.start()
    requests.get(f"{live_server}/counter")  # counter increments each call
    session = recorder.stop()

    results = Replayer(storage).run(session.id)
    # The counter value in the body will differ between original and replay.
    assert results[0].comparison["diff"]["body_match"] is False


def test_reports_are_generated(live_server, tmp_storage_dir, tmp_path):
    storage = JSONLStorage(root=tmp_storage_dir)
    recorder = Recorder(storage=storage, name="report-session")
    recorder.start()
    requests.get(f"{live_server}/ping")
    requests.get(f"{live_server}/fail")
    session = recorder.stop()

    results = Replayer(storage).run(session.id)

    html_path = generate_html_report(session, results, str(tmp_path / "r.html"))
    json_path = generate_json_report(session, results, str(tmp_path / "r.json"))

    assert "ReplayKit Report" in open(html_path).read()

    import json

    payload = json.loads(open(json_path).read())
    assert payload["summary"]["total_events"] == 2
