"""Structured JSON logging configuration for AnvilOps.

Provides a JSON formatter suitable for CloudWatch / ELK ingestion and a
middleware that attaches a correlation ID (``X-Request-ID``) to every log
record emitted during request processing.

Usage — called once at application startup::

    from app.core.logging import configure_logging
    configure_logging(debug=settings.DEBUG)
"""

import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

# ContextVar holds the current request's correlation ID so that *any*
# logger in the call-chain can include it without explicit plumbing.
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class JSONFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object.

    Fields: timestamp, level, logger, message, request_id, plus any
    extra keys attached by the caller (e.g. ``server_request_id``).
    """

    def format(self, record: logging.LogRecord) -> str:
        import json

        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get("-"),
        }

        if record.exc_info and record.exc_info[1] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Merge any extra keys the caller passed via ``logger.info("msg", extra={...})``
        for key in ("server_request_id", "task_id", "duration_ms"):
            value = getattr(record, key, None)
            if value is not None:
                log_entry[key] = value

        return json.dumps(log_entry, default=str)


def configure_logging(*, debug: bool = False) -> None:
    """Set up the root logger with the appropriate formatter.

    * **debug=True** (local dev): human-readable coloured output.
    * **debug=False** (production / container): single-line JSON.
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)

    # Remove any pre-existing handlers (e.g. from uvicorn defaults)
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)

    if debug:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
                datefmt="%H:%M:%S",
            )
        )
    else:
        handler.setFormatter(JSONFormatter())

    root.addHandler(handler)

    # Quiet noisy third-party loggers
    for name in ("uvicorn.access", "httpcore", "httpx", "asyncio"):
        logging.getLogger(name).setLevel(logging.WARNING)


def generate_request_id() -> str:
    """Return a compact unique request ID (first 12 hex chars of a UUID4)."""
    return uuid.uuid4().hex[:12]
