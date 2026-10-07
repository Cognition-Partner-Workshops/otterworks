"""Named loggers with structured (one JSON object per line) output.

DAG code logs through ``logging.getLogger(__name__)``. Inside a task Airflow routes those
records into the task log with its own prefix; ``log_event`` renders the message itself as a
JSON object so the payload stays machine-parseable there (CloudWatch, Datadog, ELK JSON
extraction). ``StructuredFormatter`` renders the whole record as JSON for handlers we own,
e.g. local runs or an Airflow ``logging_config_class``.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

EVENT_ATTR = "otterworks_event"

_RESERVED = frozenset(vars(logging.makeLogRecord({}))) | {"message", "asctime", EVENT_ATTR}

# Record metadata the formatter owns; a payload field with one of these names is kept as
# ``field_<name>`` instead of replacing it.
ENVELOPE_KEYS = frozenset({"timestamp", "level", "logger"})


def get_logger(name: str) -> logging.Logger:
    """Return the named logger; call as ``get_logger(__name__)``."""
    return logging.getLogger(name)


def _merge(payload: dict[str, Any], fields: dict[str, Any]) -> None:
    for key, value in fields.items():
        payload[f"field_{key}" if key in ENVELOPE_KEYS else key] = value


def _dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields: Any) -> None:
    """Log ``event`` with key/value ``fields`` as a single JSON object."""
    payload = {"event": event, **fields}
    logger.log(level, _dumps(payload), extra={EVENT_ATTR: payload})


class StructuredFormatter(logging.Formatter):
    """Format a record as one JSON line: timestamp, level, logger, message or event fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
        }
        event = getattr(record, EVENT_ATTR, None)
        if isinstance(event, dict):
            _merge(payload, event)
        else:
            payload["message"] = record.getMessage()
        _merge(payload, {k: v for k, v in vars(record).items() if k not in _RESERVED})
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return _dumps(payload)
