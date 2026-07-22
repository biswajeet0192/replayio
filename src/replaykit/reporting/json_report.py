"""JSON report export."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from ..core.models import Session
from ..core.replayer import ReplayResult


def generate_json_report(session: Session, results: List[ReplayResult], path: str) -> str:
    payload = {
        "session": session.to_dict(),
        "summary": _summary(results),
        "results": [
            {
                "original": r.original.to_dict(),
                "replay": r.replay.to_dict() if r.replay else None,
                "comparison": r.comparison,
            }
            for r in results
        ],
    }
    Path(path).write_text(json.dumps(payload, indent=2))
    return path


def _summary(results: List[ReplayResult]) -> dict:
    total = len(results)
    replayed = [r for r in results if not r.comparison.get("skipped")]
    matched = [r for r in replayed if r.comparison.get("status_match")]
    return {
        "total_events": total,
        "replayed": len(replayed),
        "skipped": total - len(replayed),
        "status_matched": len(matched),
        "status_mismatched": len(replayed) - len(matched),
    }
