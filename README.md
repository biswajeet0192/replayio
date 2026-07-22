# replayio

**Record real HTTP and SQL traffic. Replay it later. Catch drift before your users do.**

[![PyPI version](https://img.shields.io/pypi/v/replayio.svg)](https://pypi.org/project/replayio/)
[![Python versions](https://img.shields.io/pypi/pyversions/replayio.svg)](https://pypi.org/project/replayio/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/yourname/replayio/blob/main/LICENSE)

When something breaks in production, you usually have logs, metrics, and a stack trace —
but not the *actual* request that caused it. `replayio` transparently records every
HTTP call and SQL query your application makes into a **replay session**, with **zero
code changes**. Later, you can replay that exact session against staging, a new build,
or a migrated database, and get a side-by-side diff of what changed.

Think of it as **Git for backend traffic**.

```bash
pip install replayio
```

---

## Why replayio?

- 🪶 **Zero code changes.** Point it at your app; it patches `requests` / `httpx` /
  SQLAlchemy at the library level. No decorators, no middleware wiring required.
- 🔌 **Storage independent.** Ships with JSONL (flat files) and SQLite backends.
  Swap in your own by implementing one interface.
- ⚡ **Built for the hot path.** Recording never blocks your application — events are
  pushed to an in-memory queue and flushed in batches by a background thread.
- 🔁 **Replay & compare, not just log.** Re-execute recorded HTTP requests (and,
  optionally, read-only SQL queries) and get a structured diff: status codes, response
  bodies, latency deltas.
- 📊 **Reports you can actually read.** One-command HTML and JSON reports, no
  dashboard server required.
- 🧩 **Small, pluggable core.** Adapters, storage backends, and reporters are all
  swappable — extend it without forking it.

---

## Quick start

### 1. Record a session

```python
from replayio import Recorder

recorder = Recorder(name="checkout-flow")
recorder.start()

# ... your application code runs normally ...
# every requests.get/post/put/... call is transparently recorded

session = recorder.stop()
print(f"Recorded {session.event_count} events in session {session.id}")
```

Or use it as a context manager:

```python
from replayio import Recorder
import requests

with Recorder(name="checkout-flow") as recorder:
    requests.post("https://api.example.com/orders", json={"item": 42})

print(recorder.last_session.id)
```

### 2. Replay it later

```python
from replayio import Replayer, JSONLStorage

storage = JSONLStorage()  # defaults to .replayio/sessions
results = Replayer(storage).run(session.id)

for r in results:
    print(r.original.operation, r.comparison["status_match"], r.comparison["duration_delta_ms"])
```

### 3. Generate a report

```python
from replayio import generate_html_report

generate_html_report(session, results, "report.html")
```

Or do all of this from the command line:

```bash
replayio sessions                        # list recorded sessions
replayio replay <session_id> --export html json
replayio export <session_id> --format html
```

---

## What gets recorded

| Adapter | Library | Status |
|---|---|---|
| HTTP | `requests` | ✅ stable |
| HTTP | `httpx` (sync client) | ✅ stable |
| SQL | `SQLAlchemy` engines | ✅ stable |
| SQL | raw `psycopg` / `sqlite3` | 🔜 planned |
| Redis | `redis-py` | 🔜 planned |
| Kafka | `kafka-python` | 🔜 planned |

Every adapter normalizes its library's calls into one common `ReplayEvent` schema, so
storage, replay, and reporting never need to know which library originally produced
the event.

## Recording SQL with SQLAlchemy

```python
from sqlalchemy import create_engine
from replayio import Recorder

engine = create_engine("postgresql://user:pass@localhost/mydb")

recorder = Recorder(name="order-flow", sqlalchemy_engine=engine)
recorder.start()
# ... run queries through `engine` as usual ...
session = recorder.stop()
```

By default, replay only re-executes **read-only** (`SELECT`) queries — replaying an
`INSERT`/`UPDATE`/`DELETE` against a live database is rarely what you want without
opting in explicitly:

```python
from replayio import Replayer

Replayer(storage, sqlalchemy_engine=engine, allow_mutations=True).run(session.id)
```

---

## Choosing a storage backend

```python
from replayio import JSONLStorage, SQLiteStorage

# Flat files, zero dependencies, human-readable — good default.
storage = JSONLStorage(root=".replayio/sessions")

# Better for larger sessions or querying sessions programmatically.
storage = SQLiteStorage(path=".replayio/replayio.db")
```

Both implement the same `StorageBackend` interface, so recorders, replayers, and the
CLI all work identically regardless of which one you choose. Implement the interface
yourself to add PostgreSQL, S3, or anything else.

---

## Configuration

`replayio` can be configured via a `replayio.yaml` file or environment variables
(`REPLAYKIT_<FIELD>`, e.g. `REPLAYKIT_STORAGE_BACKEND=sqlite`):

```yaml
storage:
  backend: sqlite
  path: .replayio/replayio.db

recording:
  http: true
  httpx: false
  sqlalchemy: false

batch_size: 100
flush_interval: 1.0

output:
  html: true
  json: true
```

YAML config is optional — install with `pip install replayio[yaml]` to enable it, or
just use environment variables / the Python API directly.

---

## Installation

```bash
# Core (requests + JSONL/SQLite storage)
pip install replayio

# With httpx support
pip install replayio[httpx]

# With SQLAlchemy support
pip install replayio[sqlalchemy]

# Everything
pip install replayio[all]
```

Requires Python 3.9+.

---

## How it works

```
 Application
      │
      ▼
 Adapter layer (requests / httpx / SQLAlchemy)
      │
      ▼
 Event normalizer  →  ReplayEvent
      │
      ▼
 Background queue (batched, non-blocking)
      │
      ▼
 Storage backend (JSONL / SQLite / your own)
      │
      ▼
 Replayer  →  Comparator  →  HTML / JSON report
```

Recording overhead is kept off the request's critical path: adapters push a normalized
`ReplayEvent` onto an in-memory queue, and a single background thread drains it in
batches before writing to storage.

## Testing this package yourself

The repository includes both an automated `pytest` suite and two standalone scripts
that don't require `pytest` at all:

```bash
git clone https://github.com/yourname/replayio
cd replayio
pip install -e ".[dev]"

pytest                          # automated test suite
python scripts/manual_test.py   # human-readable smoke test, prints PASS/FAIL per check
python scripts/load_test.py --requests 2000 --concurrency 50   # throughput + data-loss check
```

## Roadmap

| Version | Focus |
|---|---|
| v1.0 (current) | Core recording, replay, JSONL/SQLite storage, `requests`/`httpx`/SQLAlchemy adapters, CLI |
| v1.1 | Redis adapter, plugin system, sensitive-field masking |
| v1.2 | Kafka/RabbitMQ adapters, PostgreSQL storage, parallel replay |
| v1.5 | Web dashboard, OpenTelemetry integration, distributed recording workers |
| v2.0 | Cluster mode, remote recording agents, cloud storage, scheduled replay |

## Contributing

Issues and pull requests are welcome. Please open an issue before starting large
changes so we can agree on direction first.

## License

MIT — see [LICENSE](LICENSE).
