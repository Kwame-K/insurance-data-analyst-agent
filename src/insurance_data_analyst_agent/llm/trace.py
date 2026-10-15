from __future__ import annotations

from contextvars import ContextVar

routing_provider_var: ContextVar[str] = ContextVar(
    "routing_provider",
    default="deterministic",
)
