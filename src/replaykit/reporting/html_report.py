"""HTML report export - a single self-contained, dependency-free file."""
from __future__ import annotations

import html
from pathlib import Path
from typing import List

from ..core.models import Session
from ..core.replayer import ReplayResult
from .json_report import _summary

_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>ReplayKit Report - {session_name}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem; color: #1a1a1a; background: #fafafa; }}
  h1 {{ margin-bottom: 0.25rem; }}
  .muted {{ color: #666; }}
  .summary {{ display: flex; gap: 1rem; margin: 1.5rem 0; flex-wrap: wrap; }}
  .card {{ background: white; border: 1px solid #e2e2e2; border-radius: 8px; padding: 1rem 1.5rem; min-width: 120px; }}
  .card .n {{ font-size: 1.6rem; font-weight: 700; }}
  table {{ width: 100%; border-collapse: collapse; background: white; }}
  th, td {{ text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid #eee; font-size: 0.9rem; }}
  th {{ background: #f0f0f0; position: sticky; top: 0; }}
  .ok {{ color: #0a7d2c; font-weight: 600; }}
  .fail {{ color: #b3261e; font-weight: 600; }}
  .skip {{ color: #999; }}
  code {{ background: #f2f2f2; padding: 0.1rem 0.3rem; border-radius: 4px; }}
</style>
</head>
<body>
  <h1>ReplayKit Report</h1>
  <p class="muted">Session <code>{session_id}</code> &middot; {session_name} &middot; {event_count} events</p>

  <div class="summary">
    <div class="card"><div class="n">{total_events}</div><div>Total events</div></div>
    <div class="card"><div class="n">{replayed}</div><div>Replayed</div></div>
    <div class="card"><div class="n">{skipped}</div><div>Skipped</div></div>
    <div class="card"><div class="n">{status_matched}</div><div>Matched</div></div>
    <div class="card"><div class="n">{status_mismatched}</div><div>Mismatched</div></div>
  </div>

  <table>
    <thead>
      <tr>
        <th>Adapter</th><th>Operation</th><th>Status</th>
        <th>Original (ms)</th><th>Replay (ms)</th><th>&Delta; (ms)</th><th>Result</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</body>
</html>
"""

_ROW_TEMPLATE = """<tr>
  <td>{adapter}</td>
  <td><code>{operation}</code></td>
  <td>{status_class_html}</td>
  <td>{orig_ms}</td>
  <td>{replay_ms}</td>
  <td>{delta_ms}</td>
  <td>{result_html}</td>
</tr>"""


def generate_html_report(session: Session, results: List[ReplayResult], path: str) -> str:
    summary = _summary(results)
    rows = "\n".join(_render_row(r) for r in results)

    output = _TEMPLATE.format(
        session_name=html.escape(session.name),
        session_id=session.id,
        event_count=session.event_count,
        rows=rows,
        **summary,
    )
    Path(path).write_text(output)
    return path


def _render_row(r: ReplayResult) -> str:
    c = r.comparison
    if c.get("skipped"):
        return _ROW_TEMPLATE.format(
            adapter=html.escape(r.original.adapter),
            operation=html.escape(r.original.operation),
            status_class_html='<span class="skip">skipped</span>',
            orig_ms=r.original.duration_ms,
            replay_ms="-",
            delta_ms="-",
            result_html='<span class="skip">not replayed</span>',
        )

    ok = c.get("status_match") and all(c.get("diff", {}).values())
    result_html = '<span class="ok">match</span>' if ok else '<span class="fail">mismatch</span>'
    status_html = (
        '<span class="ok">success</span>'
        if r.original.status == "success"
        else '<span class="fail">error</span>'
    )
    return _ROW_TEMPLATE.format(
        adapter=html.escape(r.original.adapter),
        operation=html.escape(r.original.operation),
        status_class_html=status_html,
        orig_ms=c.get("original_duration_ms"),
        replay_ms=c.get("replay_duration_ms"),
        delta_ms=c.get("duration_delta_ms"),
        result_html=result_html,
    )
