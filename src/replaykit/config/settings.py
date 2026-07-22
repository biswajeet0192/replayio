"""Configuration loading.

Supports a YAML file (optional dependency) or plain environment variables,
so the "zero external dependencies" goal holds even when no config file
is present.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class Settings:
    storage_backend: str = "jsonl"           # "jsonl" | "sqlite"
    storage_path: str = ".replayio/sessions"
    http: bool = True
    httpx: bool = False
    sqlalchemy: bool = False
    batch_size: int = 100
    flush_interval: float = 1.0
    html_report: bool = True
    json_report: bool = True
    extra: Dict[str, Any] = field(default_factory=dict)


def load_settings(path: Optional[str] = None) -> Settings:
    """Load settings from a YAML file if present, then apply env var overrides.

    Environment variables take the form ``REPLAYKIT_<FIELD>`` (uppercase),
    e.g. ``REPLAYKIT_STORAGE_BACKEND=sqlite``.
    """
    data: Dict[str, Any] = {}

    config_path = path or "replayio.yaml"
    if Path(config_path).exists():
        try:
            import yaml  # optional dependency

            raw = yaml.safe_load(Path(config_path).read_text()) or {}
            data.update(_flatten(raw))
        except ImportError:
            pass  # PyYAML not installed - fall back to defaults/env only

    settings = Settings(**{k: v for k, v in data.items() if k in Settings.__annotations__})

    for field_name in Settings.__annotations__:
        env_key = f"REPLAYKIT_{field_name.upper()}"
        if env_key in os.environ:
            raw_value = os.environ[env_key]
            setattr(settings, field_name, _coerce(raw_value, field_name, settings))

    return settings


def _flatten(raw: Dict[str, Any]) -> Dict[str, Any]:
    flat: Dict[str, Any] = {}
    storage = raw.get("storage", {})
    flat["storage_backend"] = storage.get("backend", "jsonl")
    flat["storage_path"] = storage.get("path", ".replayio/sessions")

    recording = raw.get("recording", {})
    flat["http"] = recording.get("http", True)
    flat["httpx"] = recording.get("httpx", False)
    flat["sqlalchemy"] = recording.get("sqlalchemy", False)
    flat["batch_size"] = raw.get("batch_size", 100)
    flat["flush_interval"] = raw.get("flush_interval", 1.0)

    output = raw.get("output", {})
    flat["html_report"] = output.get("html", True)
    flat["json_report"] = output.get("json", True)
    return flat


def _coerce(raw_value: str, field_name: str, settings: Settings) -> Any:
    current = getattr(settings, field_name)
    if isinstance(current, bool):
        return raw_value.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(current, int):
        return int(raw_value)
    if isinstance(current, float):
        return float(raw_value)
    return raw_value
