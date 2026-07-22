"""Adapter for the `httpx` library (sync client only in v1).

httpx is optional - if it is not installed, HTTPXAdapter simply cannot be
constructed (ImportError surfaces at patch() time), everything else keeps
working.
"""
from __future__ import annotations

import json
import time
from typing import Any, Optional

from ..core.models import ReplayEvent, new_id
from .base import Adapter


class HTTPXAdapter(Adapter):
    name = "http"  # normalized alongside `requests` - same event shape

    def __init__(self, recorder: "Any"):
        self._recorder = recorder
        self._original_send = None

    def patch(self) -> None:
        import httpx

        if self._original_send is not None:
            return

        self._original_send = httpx.Client.send
        original_send = self._original_send
        adapter = self

        def patched_send(client_self, request, *args, **kwargs):
            start = time.perf_counter()
            response = None
            error: Optional[Exception] = None
            try:
                response = original_send(client_self, request, *args, **kwargs)
                return response
            except Exception as exc:  # noqa: BLE001
                error = exc
                raise
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                adapter._record(request, response, duration_ms, error)

        httpx.Client.send = patched_send

    def unpatch(self) -> None:
        import httpx

        if self._original_send is not None:
            httpx.Client.send = self._original_send
            self._original_send = None

    def _record(self, request, response, duration_ms, error) -> None:
        request_data = {
            "method": request.method,
            "url": str(request.url),
            "headers": dict(request.headers),
            "body": _safe_body(request),
        }
        if response is not None:
            response_data = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": _safe_text(response),
            }
            status = "success" if response.is_success else "error"
        else:
            response_data = {"error": str(error)}
            status = "error"

        event = ReplayEvent(
            id=new_id(),
            session_id=self._recorder.session.id,
            adapter=self.name,
            operation=request.method.upper(),
            request=request_data,
            response=response_data,
            duration_ms=round(duration_ms, 3),
            status=status,
        )
        self._recorder.record_event(event)


def _safe_body(request, limit: int = 20000) -> Optional[str]:
    try:
        content = request.read()
        return content.decode("utf-8", errors="replace")[:limit]
    except Exception:  # noqa: BLE001
        return None


def _safe_text(response, limit: int = 20000) -> Optional[str]:
    try:
        return response.text[:limit]
    except Exception:  # noqa: BLE001
        return None
