"""Centralized structured diagnostics and typed error codes for Cuepoint."""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone

SENSITIVE_KEYS = frozenset({"key", "password", "passwd", "secret", "token", "blob", "sqlcipher_key"})

ERROR_CODES = frozenset({
    "SOURCE_NOT_FOUND",
    "SOURCE_UNREADABLE",
    "SNAPSHOT_INCONSISTENT",
    "SQLCIPHER_UNAVAILABLE",
    "DATABASE_DECRYPT_FAILED",
    "DATABASE_SCHEMA_INVALID",
    "TRACK_NOT_FOUND",
    "TRACK_AMBIGUOUS",
    "ANALYSIS_FILE_MISSING",
    "PYTHON_WORKER_UNAVAILABLE",
    "IPC_TIMEOUT",
    "NETWORK_INTERFACE_UNAVAILABLE",
    "DJ_LINK_PORT_UNAVAILABLE",
    "REKORDBOX_NOT_RUNNING",
    "REKORDBOX_UI_UNAVAILABLE",
    "MEDIA_NOT_FOUND",
})


class CuepointError(ValueError):
    """Domain error carrying a structured diagnostic errorCode."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code if code in ERROR_CODES else "SOURCE_UNREADABLE"
        self.message = message


def new_correlation_id() -> str:
    return uuid.uuid4().hex[:12]


def _sanitize(extra: dict) -> dict:
    clean = {}
    for key, value in extra.items():
        if key.lower() in SENSITIVE_KEYS:
            clean[key] = "[REDACTED]"
        elif isinstance(value, (str, int, float, bool)) or value is None:
            clean[key] = value
        else:
            clean[key] = str(value)
    return clean


def emit_log(
    severity: str,
    subsystem: str,
    event: str,
    message: str = "",
    *,
    correlation_id: str | None = None,
    duration_ms: float | None = None,
    **extra,
) -> None:
    """Write a single JSONL structured log record to stderr (never stdout)."""
    record = {
        "Timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "Severity": str(severity or "INFO").upper(),
        "Subsystem": subsystem,
        "Event": event,
        "Correlation-ID": correlation_id or "-",
        "Duration": round(float(duration_ms), 3) if duration_ms is not None else None,
        "Message": str(message or ""),
    }
    if extra:
        record["Context"] = _sanitize(extra)
    try:
        sys.stderr.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
        sys.stderr.flush()
    except OSError:
        pass
