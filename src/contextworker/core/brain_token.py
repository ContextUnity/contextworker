"""Worker → Brain service token factory.

Provides a single-source ContextToken for all Worker service calls to Brain.
Every BrainClient created by the Worker should use this token.

Usage::

    from contextworker.core.brain_token import get_brain_service_token

    token = get_brain_service_token()
    client = BrainClient(host=brain_host, mode="grpc", token=token)
"""

from __future__ import annotations

from functools import lru_cache

from contextcore.permissions import Permissions
from contextcore.tokens import ContextToken

__all__ = ["get_brain_service_token"]


@lru_cache(maxsize=1)
def get_brain_service_token() -> ContextToken:
    """Return a cached ContextToken for Worker → Brain calls.

    Grants the minimal set of permissions needed by the Worker:
    - brain:read / brain:write — episodic memory, knowledge ops
    - memory:read / memory:write — entity memory, fact upsert
    - trace:write — sub-agent step recording
    """
    return ContextToken(
        token_id="worker-brain-service",
        permissions=(
            Permissions.BRAIN_READ,
            Permissions.BRAIN_WRITE,
            Permissions.MEMORY_READ,
            Permissions.MEMORY_WRITE,
            Permissions.TRACE_WRITE,
        ),
    )
