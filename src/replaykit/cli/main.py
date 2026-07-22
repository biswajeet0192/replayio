"""ReplayKit command line interface.

    replayio sessions
    replayio replay <session_id>
    replayio export <session_id> --format html|json
    replayio compare <session_id>
"""
from __future__ import annotations

import argparse
import sys
from typing import Optional

from ..config import load_settings
from ..core.replayer import Replayer
from ..exceptions import SessionNotFoundError
from ..reporting import generate_html_report, generate_json_report
from ..storage.jsonl_storage import JSONLStorage
from ..storage.sqlite_storage import SQLiteStorage


def _build_storage(settings):
    if settings.storage_backend == "sqlite":
        return SQLiteStorage(settings.storage_path if settings.storage_path.endswith(".db")
                              else ".replayio/replayio.db")
    return JSONLStorage(settings.storage_path)


def cmd_sessions(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    storage = _build_storage(settings)
    sessions = storage.list_sessions()
    if not sessions:
        print("No sessions recorded yet.")
        return 0
    print(f"{'SESSION ID':34} {'NAME':20} {'EVENTS':8} STARTED")
    for s in sessions:
        import datetime

        started = datetime.datetime.fromtimestamp(s.started_at).isoformat(timespec="seconds")
        print(f"{s.id:34} {s.name:20} {s.event_count:<8} {started}")
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    storage = _build_storage(settings)
    engine = None
    if args.db_url:
        from sqlalchemy import create_engine

        engine = create_engine(args.db_url)

    replayer = Replayer(storage, sqlalchemy_engine=engine, allow_mutations=args.allow_mutations)
    try:
        results = replayer.run(args.session_id)
    except SessionNotFoundError:
        print(f"Session not found: {args.session_id}", file=sys.stderr)
        return 1

    replayed = [r for r in results if not r.comparison.get("skipped")]
    matched = [r for r in replayed if r.comparison.get("status_match")]
    print(f"Replayed {len(replayed)}/{len(results)} events - {len(matched)} matched status.")

    if args.export:
        session = storage.get_session(args.session_id)
        if "html" in args.export:
            path = generate_html_report(session, results, f"{args.session_id}_report.html")
            print(f"HTML report: {path}")
        if "json" in args.export:
            path = generate_json_report(session, results, f"{args.session_id}_report.json")
            print(f"JSON report: {path}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    storage = _build_storage(settings)
    session = storage.get_session(args.session_id)
    if session is None:
        print(f"Session not found: {args.session_id}", file=sys.stderr)
        return 1

    replayer = Replayer(storage)
    results = replayer.run(args.session_id, http=False, sql=False)  # metadata-only export
    if not results:
        # No replay requested - just dump raw events for export.
        results = []

    if args.format == "html":
        path = generate_html_report(session, results, args.output or f"{args.session_id}_report.html")
    else:
        path = generate_json_report(session, results, args.output or f"{args.session_id}_report.json")
    print(f"Wrote {path}")
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    for field_name, value in settings.__dict__.items():
        print(f"{field_name}: {value}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", default=None, help="Path to replayio.yaml (optional)")

    parser = argparse.ArgumentParser(
        prog="replayio", description="Record and replay backend traffic.", parents=[common]
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_sessions = sub.add_parser("sessions", help="List recorded sessions", parents=[common])
    p_sessions.set_defaults(func=cmd_sessions)

    p_replay = sub.add_parser("replay", help="Replay a recorded session", parents=[common])
    p_replay.add_argument("session_id")
    p_replay.add_argument("--db-url", default=None, help="SQLAlchemy URL to replay SQL events against")
    p_replay.add_argument("--allow-mutations", action="store_true", help="Allow replaying INSERT/UPDATE/DELETE")
    p_replay.add_argument("--export", nargs="*", choices=["html", "json"], default=[])
    p_replay.set_defaults(func=cmd_replay)

    p_export = sub.add_parser("export", help="Export a session report without replaying", parents=[common])
    p_export.add_argument("session_id")
    p_export.add_argument("--format", choices=["html", "json"], default="html")
    p_export.add_argument("--output", default=None)
    p_export.set_defaults(func=cmd_export)

    p_config = sub.add_parser("config", help="Print resolved configuration", parents=[common])
    p_config.set_defaults(func=cmd_config)

    return parser


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
