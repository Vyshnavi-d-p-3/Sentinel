"""
Structured logging configuration.

Production deployments set ``SENTINEL_LOG_FORMAT=json`` which emits one JSON
object per log line. Local development uses a human-readable formatter. Both
modes preserve ``request_id`` and any other ``extra=`` fields.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any

_RESERVED_LOG_RECORD_ATTRS = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys()
) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """Render records as a single-line JSON object with ``extra=`` promoted."""

    def format(self, record: logging.LogRecord) -> str:
        base: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_RECORD_ATTRS:
                continue
            if key.startswith("_"):
                continue
            base[key] = _jsonable(value)
        return json.dumps(base, default=str, ensure_ascii=False)


def _jsonable(value: Any) -> Any:
    """Coerce values into something ``json.dumps`` can handle without surprises."""
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    if isinstance(value, list | tuple | set):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    try:
        return str(value)
    except Exception:  # noqa: BLE001
        return "<unrepr>"


def configure_logging() -> None:
    """Idempotent root-logger configuration used by ``app.main``."""
    level_name = os.environ.get("SENTINEL_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    fmt = os.environ.get("SENTINEL_LOG_FORMAT", "text").lower()

    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s [rid=%(request_id)s] %(message)s",
                defaults={"request_id": "-"},
            )
        )

    root = logging.getLogger()
    # Remove any pre-existing handlers installed by uvicorn or tests to keep
    # formatting consistent.
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)
    root.setLevel(level)

    # Quiet down noisy third-party loggers — SQLAlchemy's engine logs are very
    # verbose at INFO level and contain raw SQL which we don't want in access
    # logs.
    for noisy in ("sqlalchemy.engine", "sqlalchemy.pool", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
