"""Shared pytest fixtures: an in-process Flask server + tmp storage dirs."""
from __future__ import annotations

import shutil
import threading
import time
from pathlib import Path

import pytest

from ._test_server import app


@pytest.fixture(scope="session")
def live_server():
    """Run the test Flask app on a background thread for the whole test session."""
    port = 8945
    thread = threading.Thread(
        target=lambda: app.run(port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    thread.start()
    time.sleep(0.5)
    yield f"http://127.0.0.1:{port}"


@pytest.fixture()
def tmp_storage_dir(tmp_path: Path):
    d = tmp_path / "sessions"
    d.mkdir()
    yield str(d)
    shutil.rmtree(d, ignore_errors=True)
