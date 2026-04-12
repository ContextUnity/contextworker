"""Worker → Brain service token factory.

Thin wrapper over cu.core.tokens.get_brain_service_token().
"""

from __future__ import annotations

from contextunity.core.tokens import get_brain_service_token as _get_brain_service_token

__all__ = ["get_brain_service_token"]


def get_brain_service_token():
    """Return a cached ContextToken for Worker → Brain calls."""
    return _get_brain_service_token("worker")
