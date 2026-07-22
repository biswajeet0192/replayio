#!/usr/bin/env python3
"""
Manual, human-readable smoke test for ReplayKit.

Run this after installing the package (or with PYTHONPATH=src) to sanity
check the whole pipeline end-to-end against a local Flask server:

    python scripts/manual_test.py

No external services or internet access are required - a tiny Flask app
is started on localhost for the duration of the script.

Exit code is 0 if every check passes, 1 otherwise.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

import requests  # noqa: E402

from replayio import (  # noqa: E402
    Recorder,
    Replayer,
    JSONLStorage,
    SQLiteStorage,
    generate_html_report,
    generate_json_report,
)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

_results = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = PASS if condition else FAIL
    print(f"  [{status}] {name}" + (f" - {detail}" if detail and not condition else ""))
    _results.append(condition)


def section(title: str) -> None:
    print(f"\n== {title} ==")


def start_test_server(port: int = 8940) -> str:
    from _test_server import app

    thread = threading.Thread(
        target=lambda: app.run(port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    thread.start()
    time.sleep(0.5)
    return f"http://127.0.0.1:{port}"


def main() -> int:
    print("ReplayKit manual test\n" + "=" * 40)
    base_url = start_test_server()
    tmp_dir = Path(tempfile.mkdtemp(prefix="replaykit_manual_"))

    try:
        # 1. Recording with JSONL storage --------------------------------
        section("Recording (JSONL storage)")
        storage = JSONLStorage(root=str(tmp_dir / "jsonl_sessions"))
        recorder = Recorder(storage=storage, name="manual-jsonl")
        recorder.start()
        requests.get(f"{base_url}/ping")
        requests.post(f"{base_url}/echo", json={"hello": "world"})
        requests.get(f"{base_url}/fail")
        session = recorder.stop()

        check("session created", session is not None)
        check("3 events recorded", session.event_count == 3, f"got {session.event_count}")

        events = list(storage.iter_events(session.id))
        check("events persisted to disk", len(events) == 3, f"got {len(events)}")
        check(
            "success/error statuses captured",
            {e.status for e in events} == {"success", "error"},
        )

        # 2. Replay ---------------------------------------------------------
        section("Replay")
        results = Replayer(storage).run(session.id)
        check("all events replayed", len(results) == 3, f"got {len(results)}")
        matched = [r for r in results if r.comparison.get("status_match")]
        check("status codes matched on replay", len(matched) == 3, f"{len(matched)}/3 matched")

        # 3. Reporting --------------------------------------------------
        section("Reporting")
        html_path = generate_html_report(session, results, str(tmp_dir / "report.html"))
        json_path = generate_json_report(session, results, str(tmp_dir / "report.json"))
        check("HTML report written", Path(html_path).exists() and Path(html_path).stat().st_size > 0)
        check("JSON report written", Path(json_path).exists() and Path(json_path).stat().st_size > 0)

        import json

        payload = json.loads(Path(json_path).read_text())
        check(
            "JSON report summary matches event count",
            payload["summary"]["total_events"] == 3,
            str(payload["summary"]),
        )

        # 4. SQLite backend --------------------------------------------------
        section("Recording (SQLite storage)")
        sqlite_storage = SQLiteStorage(path=str(tmp_dir / "replayio.db"))
        with Recorder(storage=sqlite_storage, name="manual-sqlite") as sqlite_recorder:
            requests.get(f"{base_url}/counter")
            requests.get(f"{base_url}/slow")

        sqlite_session = sqlite_recorder.last_session
        check("sqlite session recorded", sqlite_session.event_count == 2)
        sessions_listed = sqlite_storage.list_sessions()
        check("sqlite lists sessions", len(sessions_listed) == 1)
        sqlite_storage.close()

        # 5. Drift detection ----------------------------------------------
        section("Drift detection (replaying a changing endpoint)")
        drift_storage = JSONLStorage(root=str(tmp_dir / "drift_sessions"))
        drift_recorder = Recorder(storage=drift_storage, name="manual-drift")
        drift_recorder.start()
        requests.get(f"{base_url}/counter")  # response body includes a counter that changes
        drift_session = drift_recorder.stop()

        drift_results = Replayer(drift_storage).run(drift_session.id)
        body_mismatch = not drift_results[0].comparison["diff"]["body_match"]
        check("body drift correctly detected", body_mismatch)

        # 6. Error handling --------------------------------------------------
        section("Error handling")
        from replayio.exceptions import RecorderStateError, SessionNotFoundError

        double_start_ok = False
        r2 = Recorder(storage=storage, name="double-start")
        r2.start()
        try:
            r2.start()
        except RecorderStateError:
            double_start_ok = True
        finally:
            r2.stop()
        check("double start() raises RecorderStateError", double_start_ok)

        missing_session_ok = False
        try:
            list(storage.iter_events("nonexistent-session-id"))
        except SessionNotFoundError:
            missing_session_ok = True
        check("unknown session id raises SessionNotFoundError", missing_session_ok)

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print("\n" + "=" * 40)
    total = len(_results)
    passed = sum(_results)
    print(f"Result: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
