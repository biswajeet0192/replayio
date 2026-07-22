"""Adapter for the `requests` library.

Patches `requests.Session.request` (the single choke point every requests
API - get/post/put/... - funnels through), so every outgoing HTTP call
made anywhere in the application is captured with zero code changes.
"""
from __future__ import annotations

import json
import time
from typing import Any, Optional

from ..core.models import ReplayEvent, new_id
from .base import Adapter


class HTTPAdapter(Adapter):
    name = "http"

    def __init__(self, recorder: "Any"):
        self._recorder = recorder
        self._original_request = None

    def patch(self) -> None:
        import requests

        if self._original_request is not None:
            return  # already patched

        self._original_request = requests.Session.request
        original_request = self._original_request
        adapter = self

        def patched_request(session_self, method, url, *args, **kwargs):
            start = time.perf_counter()
            response = None
            error: Optional[Exception] = None
            try:
                response = original_request(session_self, method, url, *args, **kwargs)
                return response
            except Exception as exc:  # noqa: BLE001 - re-raised below
                error = exc
                raise
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                adapter._record(method, url, kwargs, response, duration_ms, error)

        requests.Session.request = patched_request

    def unpatch(self) -> None:
        import requests

        if self._original_request is not None:
            requests.Session.request = self._original_request
            self._original_request = None

    def _record(self, method, url, kwargs, response, duration_ms, error) -> None:
        request_data = {
            "method": method,
            "url": url,
            "headers": _safe_json(dict(kwargs.get("headers") or {})),
            "params": _safe_json(kwargs.get("params")),
            "body": _safe_json(kwargs.get("json") if kwargs.get("json") is not None else kwargs.get("data")),
        }

        if response is not None:
            response_data = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": _safe_text(response),
            }
            status = "success" if response.ok else "error"
        else:
            response_data = {"error": str(error)}
            status = "error"

        event = ReplayEvent(
            id=new_id(),
            session_id=self._recorder.session.id,
            adapter=self.name,
            operation=str(method).upper(),
            request=request_data,
            response=response_data,
            duration_ms=round(duration_ms, 3),
            status=status,
        )
        self._recorder.record_event(event)


def _safe_json(value: Any, limit: int = 20000) -> Any:
    if value is None:
        return None
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)[:limit]


def _safe_text(response, limit: int = 20000) -> Optional[str]:
    try:
        return response.text[:limit]
    except Exception:  # noqa: BLE001
        return None
