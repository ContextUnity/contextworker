"""Worker → Brain service token factory.

Provides a single-source ContextToken for all Worker service calls to Brain.
Every BrainClient created by the Worker should use this token.

Usage::

    from contextworker.core.brain_token import get_brain_service_token

    token = get_brain_service_token()
    client = BrainClient(host=brain_host, mode="grpc", token=token)
"""

from __future__ import annotations

from contextcore.permissions import Permissions
from contextcore.tokens import mint_service_token

__all__ = ["get_brain_service_token"]

_PERMISSIONS = (
    Permissions.BRAIN_READ,
    Permissions.BRAIN_WRITE,
    Permissions.MEMORY_READ,
    Permissions.MEMORY_WRITE,
    Permissions.TRACE_WRITE,
)


def get_brain_service_token():
    """Return a cached ContextToken for Worker → Brain calls.

    Grants the minimal set of permissions needed by the Worker:
    - brain:read / brain:write — episodic memory, knowledge ops
    - memory:read / memory:write — entity memory, fact upsert
    - trace:write — sub-agent step recording

    Token has a 1-hour TTL (managed by ``mint_service_token``).
    """
    return mint_service_token("worker-brain-service", permissions=_PERMISSIONS)
