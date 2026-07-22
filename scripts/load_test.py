#!/usr/bin/env python3
"""
Load / stress test for ReplayKit's recording pipeline.

Measures:
  1. Recording overhead per HTTP call (with vs. without ReplayKit patched)
  2. Sustained throughput with many concurrent threads hammering the
     recorder simultaneously
  3. Whether every event survives the trip through the background queue
     into storage under load (no event loss)

This uses only the standard library's ThreadPoolExecutor plus `requests`
against a local Flask server, so it runs anywhere without extra
dependencies (no Locust/k6 required).

Usage:
    python scripts/load_test.py --requests 2000 --concurrency 50
"""
from __future__ import annotations

import argparse
import shutil
import statistics
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

import requests  # noqa: E402

from replayio import Recorder, SQLiteStorage  # noqa: E402


def start_test_server(port: int = 8950) -> str:
    from _test_server import app

    thread = threading.Thread(
        target=lambda: app.run(port=port, debug=False, use_reloader=False, threaded=True),
        daemon=True,
    )
    thread.start()
    time.sleep(0.5)
    return f"http://127.0.0.1:{port}"


def timed_requests(base_url: str, n: int, concurrency: int) -> list:
    """Fire n GET /ping requests using a thread pool, return latencies (ms)."""
    latencies = []
    lock = threading.Lock()

    def one_request(_i):
        start = time.perf_counter()
        requests.get(f"{base_url}/ping")
        elapsed_ms = (time.perf_counter() - start) * 1000
        with lock:
            latencies.append(elapsed_ms)

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(one_request, i) for i in range(n)]
        for f in as_completed(futures):
            f.result()

    return latencies


def summarize(label: str, latencies: list) -> None:
    latencies_sorted = sorted(latencies)
    p50 = statistics.median(latencies_sorted)
    p95 = latencies_sorted[int(len(latencies_sorted) * 0.95) - 1]
    p99 = latencies_sorted[int(len(latencies_sorted) * 0.99) - 1]
    mean = statistics.mean(latencies_sorted)
    print(
        f"{label:30} n={len(latencies_sorted):5}  "
        f"mean={mean:6.2f}ms  p50={p50:6.2f}ms  p95={p95:6.2f}ms  p99={p99:6.2f}ms"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="ReplayKit load test")
    parser.add_argument("--requests", type=int, default=1000, help="Total requests per phase")
    parser.add_argument("--concurrency", type=int, default=25, help="Concurrent worker threads")
    args = parser.parse_args()

    print("ReplayKit load test")
    print("=" * 60)
    print(f"requests/phase={args.requests}  concurrency={args.concurrency}\n")

    base_url = start_test_server()
    tmp_dir = Path(tempfile.mkdtemp(prefix="replaykit_load_"))

    try:
        # Phase 1: baseline, no recording ------------------------------
        print("Phase 1: baseline (ReplayKit not active)")
        baseline_latencies = timed_requests(base_url, args.requests, args.concurrency)
        summarize("baseline", baseline_latencies)

        # Phase 2: with recording active ------------------------------
        print("\nPhase 2: with ReplayKit recording (SQLite storage)")
        storage = SQLiteStorage(path=str(tmp_dir / "load.db"))
        recorder = Recorder(storage=storage, name="load-test", batch_size=200, flush_interval=0.5)
        recorder.start()

        t0 = time.perf_counter()
        recorded_latencies = timed_requests(base_url, args.requests, args.concurrency)
        wall_time_s = time.perf_counter() - t0

        session = recorder.stop()
        summarize("with recording", recorded_latencies)

        # Phase 3: verify no event loss ------------------------------
        print("\nPhase 3: verifying event durability")
        stored_events = list(storage.iter_events(session.id))
        print(f"  events expected : {args.requests}")
        print(f"  events recorded : {session.event_count}")
        print(f"  events persisted: {len(stored_events)}")

        no_loss = len(stored_events) == args.requests == session.event_count
        print(f"  no event loss   : {'YES' if no_loss else 'NO -- DATA LOSS DETECTED'}")

        throughput = args.requests / wall_time_s
        print(f"\n  throughput while recording: {throughput:.1f} req/s over {wall_time_s:.2f}s")

        # Overhead summary ------------------------------------------------
        baseline_mean = statistics.mean(baseline_latencies)
        recorded_mean = statistics.mean(recorded_latencies)
        overhead_ms = recorded_mean - baseline_mean
        print(f"\n  mean overhead per request: {overhead_ms:.3f} ms "
              f"({baseline_mean:.2f}ms -> {recorded_mean:.2f}ms)")

        storage.close()

        print("\n" + "=" * 60)
        if not no_loss:
            print("RESULT: FAIL (event loss under load)")
            return 1
        print("RESULT: PASS")
        return 0

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
