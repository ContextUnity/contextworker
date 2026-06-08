"""gRPC interceptor for contextunity.worker permission enforcement.
Maps each Worker RPC method to the exact permission required
and validates the ContextToken carries that permission.
Delegates to ``contextunity.core.security.ServicePermissionInterceptor``
for unified enforcement logic. Worker only owns the RPC_PERMISSION_MAP.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from contextunity.core.permissions import Permissions
from contextunity.core.security import ServicePermissionInterceptor

if TYPE_CHECKING:
    from contextunity.worker.config import WorkerConfig

# ── RPC → Permission mapping ──────────────────────────────────

RPC_PERMISSION_MAP: dict[str, str] = {
    "StartWorkflow": Permissions.WORKER_EXECUTE,
    "GetTaskStatus": Permissions.WORKER_READ,
    "ExecuteCode": Permissions.WORKER_EXECUTE,
    "RegisterSchedules": Permissions.WORKER_EXECUTE,
}


class WorkerPermissionInterceptor(ServicePermissionInterceptor):
    """Worker-specific permission interceptor.

    Thin wrapper around ``ServicePermissionInterceptor`` that pre-fills
    the Worker RPC permission map and service name.

    Usage::

        interceptor = WorkerPermissionInterceptor()
        server = grpc.aio.server(interceptors=[interceptor])
    """

    def __init__(self, *, shield_url: str = "", config: "WorkerConfig | None" = None) -> None:
        """Initialize the worker permission interceptor."""
        super().__init__(
            RPC_PERMISSION_MAP,
            service_name="Worker",
            shield_url=shield_url,
            config=config,
        )


__all__ = [
    "WorkerPermissionInterceptor",
    "RPC_PERMISSION_MAP",
]
