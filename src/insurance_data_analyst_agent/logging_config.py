from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from uuid import uuid4

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")


def new_correlation_id() -> str:
    """Return a new random correlation identifier."""
    return str(uuid4())


def set_correlation_id(value: str) -> None:
    """Bind a correlation identifier to the current request context."""
    correlation_id_var.set(value)


def get_correlation_id() -> str:
    """Return the correlation identifier of the current context."""
    return correlation_id_var.get()


class CorrelationIdFilter(logging.Filter):
    """Inject the current correlation_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id()
        return True


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging once, writing to stderr."""
    handler = logging.StreamHandler(sys.stderr)
    handler.addFilter(CorrelationIdFilter())
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(correlation_id)s] %(name)s: %(message)s"
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
