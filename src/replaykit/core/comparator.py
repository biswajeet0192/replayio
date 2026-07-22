"""Comparator: diffs an original event against its replay."""
from __future__ import annotations

from typing import Any, Dict, Optional

from .models import ReplayEvent


def compare(original: ReplayEvent, replay: Optional[ReplayEvent]) -> Dict[str, Any]:
    """Compare a recorded event with the result of replaying it.

    Returns a plain dict (not a dataclass) so it can be serialized directly
    into JSON/HTML reports.
    """
    if replay is None:
        return {
            "event_id": original.id,
            "adapter": original.adapter,
            "operation": original.operation,
            "skipped": True,
            "reason": "not replayed (unsupported adapter, missing engine, or mutating query)",
        }

    status_match = original.status == replay.status
    duration_delta_ms = round(replay.duration_ms - original.duration_ms, 3)

    diff: Dict[str, Any] = {}
    if original.adapter == "http":
        diff["status_code_match"] = original.response.get("status_code") == replay.response.get(
            "status_code"
        )
        diff["body_match"] = original.response.get("body") == replay.response.get("body")
    elif original.adapter == "sql":
        diff["row_count_match"] = original.response.get("row_count") == replay.response.get(
            "row_count"
        )

    return {
        "event_id": original.id,
        "adapter": original.adapter,
        "operation": original.operation,
        "status_match": status_match,
        "original_duration_ms": original.duration_ms,
        "replay_duration_ms": replay.duration_ms,
        "duration_delta_ms": duration_delta_ms,
        "faster": duration_delta_ms < 0,
        "diff": diff,
        "skipped": False,
    }
