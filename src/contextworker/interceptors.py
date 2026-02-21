"""gRPC interceptor for ContextWorker permission enforcement.

Maps each Worker RPC method to the exact permission required
and validates the ContextToken carries that permission.

Delegates to ``contextcore.security.ServicePermissionInterceptor``
for unified enforcement logic. Worker only owns the RPC_PERMISSION_MAP.
"""

from __future__ import annotations

from contextcore.permissions import Permissions
from contextcore.security import EnforcementMode, ServicePermissionInterceptor

# ── RPC → Permission mapping ──────────────────────────────────

RPC_PERMISSION_MAP: dict[str, str] = {
    "StartWorkflow": Permissions.WORKER_EXECUTE,
    "GetTaskStatus": Permissions.WORKER_READ,
    "ExecuteCode": Permissions.WORKER_EXECUTE,
}


class WorkerPermissionInterceptor(ServicePermissionInterceptor):
    """Worker-specific permission interceptor.

    Thin wrapper around ``ServicePermissionInterceptor`` that pre-fills
    the Worker RPC permission map and service name.

    Usage::

        interceptor = WorkerPermissionInterceptor(enforcement=EnforcementMode.WARN)
        server = grpc.aio.server(interceptors=[interceptor])
    """

    def __init__(self, *, enforcement: EnforcementMode | None = None) -> None:
        super().__init__(
            RPC_PERMISSION_MAP,
            service_name="Worker",
            enforcement=enforcement,
        )


__all__ = [
    "WorkerPermissionInterceptor",
    "RPC_PERMISSION_MAP",
]
