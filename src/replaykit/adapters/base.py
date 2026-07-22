"""Adapter interface.

An Adapter wraps a third-party library so that its operations are
transparently converted into ReplayEvents without requiring the
application to change any of its own code. patch() must be idempotent-safe
to call once per recording session, and unpatch() must fully restore the
original behaviour.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class Adapter(ABC):
    name: str = "base"

    @abstractmethod
    def patch(self) -> None:
        """Install interception hooks."""

    @abstractmethod
    def unpatch(self) -> None:
        """Remove interception hooks and restore original behaviour."""
