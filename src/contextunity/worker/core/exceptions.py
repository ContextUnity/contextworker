"""Exception hierarchy for contextunity.worker.

Service-specific exceptions with stable error codes for gRPC mapping.
All codes use the ``WORKER_`` prefix so the prefix-based fallback in
``core/grpc_errors.py`` maps them to ``grpc.StatusCode.INTERNAL`` by default.

Base class and infrastructure exceptions (ConfigurationError, SecurityError, etc.)
live in ``contextunity.core.exceptions`` — import them directly from there.

Usage::

    from contextunity.worker.core.exceptions import (
        ContextworkerError,
        WorkerValidationError,
    )
    from contextunity.core.exceptions import ConfigurationError
"""

from __future__ import annotations

from contextunity.core.exceptions import ContextUnityError, register_error


@register_error("WORKER_ERROR")
class ContextworkerError(ContextUnityError):
    """Base exception for contextunity.worker.

    Inherits from ContextUnityError so that centralized gRPC error handlers
    in contextunity.core catch worker-specific exceptions automatically.
    """

    code: str = "WORKER_ERROR"
    message: str = "Worker service error"


@register_error("WORKER_VALIDATION_ERROR")
class WorkerValidationError(ContextworkerError):
    """Input or data validation failed."""

    code: str = "WORKER_VALIDATION_ERROR"
    message: str = "Input or data validation failed"
