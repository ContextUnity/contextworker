"""Worker → Brain service token factory.

Thin wrapper over contextunity.core.tokens.get_brain_service_token().
"""

from __future__ import annotations

from collections.abc import Iterable

from contextunity.core import ContextToken
from contextunity.core.tokens import get_brain_service_token as _get_brain_service_token

__all__ = ["get_brain_service_token"]


def get_brain_service_token(*, allowed_tenants: Iterable[str] = ()) -> ContextToken:
    """Return a cached ContextToken for Worker → Brain calls."""
    return _get_brain_service_token("worker", allowed_tenants=allowed_tenants)
