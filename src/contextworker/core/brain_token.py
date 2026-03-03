"""Worker → Brain service token factory.

Thin wrapper over contextcore.tokens.get_brain_service_token().
"""

from __future__ import annotations

from contextcore.tokens import get_brain_service_token as _get_brain_service_token

__all__ = ["get_brain_service_token"]


def get_brain_service_token():
    """Return a cached ContextToken for Worker → Brain calls."""
    return _get_brain_service_token("worker")
