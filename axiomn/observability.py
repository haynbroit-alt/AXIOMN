"""Structured logging for AXIOMN.

Once there is real traffic, "what did the runtime decide, and what did it cost"
has to be answerable from logs — grep-able per request, not buried in a print.
This module emits one JSON object per log line (request id, route, model, cost,
latency, success) so a log aggregator can slice by any field.

Standard-library only — no new dependency. Format is controlled by
``AXIOMN_LOG_FORMAT`` (``json`` default, ``text`` for human-readable local dev)
and level by ``AXIOMN_LOG_LEVEL`` (default ``INFO``).
"""
from __future__ import annotations

import json
import logging
import os
from contextvars import ContextVar

# The id of the request currently being served, so any log line emitted deep in
# the pipeline can be correlated back to the HTTP request that caused it.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

logger = logging.getLogger("axiomn")

# Keys that are part of a LogRecord by default; everything else an emitter
# attaches via `extra=` is treated as a structured field and serialized.
_RESERVED = set(
    logging.makeLogRecord({}).__dict__
) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    """Serialize each record as a single-line JSON object.

    Any non-standard attribute set through ``logger.info(..., extra={...})`` is
    promoted to a top-level field, so `record(route=..., cost=...)` is queryable
    without parsing the message string.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        rid = request_id_var.get()
        if rid is not None:
            payload["request_id"] = rid
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging() -> None:
    """Install the configured handler on the ``axiomn`` logger (idempotent)."""
    level = os.environ.get("AXIOMN_LOG_LEVEL", "INFO").upper()
    fmt = os.environ.get("AXIOMN_LOG_FORMAT", "json").lower()

    handler = logging.StreamHandler()
    if fmt == "text":
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
    else:
        handler.setFormatter(JsonFormatter())

    logger.setLevel(level)
    # Replace prior handlers so repeated imports (tests, reloads) don't stack up
    # duplicate lines, and don't double-emit through the root logger.
    logger.handlers = [handler]
    logger.propagate = False
