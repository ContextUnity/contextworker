"""WorkerService - gRPC service for contextunity.worker."""

from __future__ import annotations

import grpc

# Import generated protobuf stubs — fail-closed: service MUST NOT start
# without gRPC contracts (Secure by Default).
from contextunity.core import (
    ContextUnit,
    contextunit_pb2,
    get_contextunit_logger,
    worker_pb2_grpc,
)

from .config import get_config

logger = get_contextunit_logger(__name__)


def parse_unit(request) -> ContextUnit:
    """Parse protobuf request to ContextUnit."""
    return ContextUnit.from_protobuf(request)


def _get_verified_token(context):
    """Get the verified token from VerifiedAuthContext (set by interceptor).

    Always fail-closed: no token = abort UNAUTHENTICATED.

    Returns:
        ContextToken — verified and non-expired.

    Raises:
        grpc.RpcError on missing/expired token.
    """
    from contextunity.core.authz.context import get_auth_context

    auth_ctx = get_auth_context()
    if auth_ctx is not None:
        return auth_ctx.token

    context.abort(
        grpc.StatusCode.UNAUTHENTICATED,
        "No verified auth context found — fail-closed security enforced",
    )


def _authorize_worker(context, token, *, permission: str, rpc_name: str, tenant_id: str | None = None):
    """Run canonical authorization check for a Worker RPC.

    Args:
        context: gRPC servicer context (for abort).
        token: Verified ContextToken.
        permission: Required permission string.
        rpc_name: RPC method name (for audit).
        tenant_id: Target tenant to check binding (optional).

    Raises:
        grpc.RpcError on authorization failure.
    """
    from contextunity.core.authz import authorize, get_auth_context

    auth_ctx = get_auth_context()
    decision = authorize(
        auth_ctx if auth_ctx is not None else token,
        permission=permission,
        tenant_id=tenant_id,
        service="worker",
        rpc_name=rpc_name,
    )
    if decision.denied:
        context.abort(grpc.StatusCode.PERMISSION_DENIED, decision.reason)


class WorkerService(worker_pb2_grpc.WorkerServiceServicer):
    """gRPC service for contextunity.worker.

    Handles workflow triggers and sub-agent execution via ContextUnit protocol.

    Authorization is enforced at two layers:
    1. ``WorkerPermissionInterceptor`` — RPC-level permission check
    2. Handler-level — tenant binding and resource-level checks
    """

    def __init__(self, temporal_host: str | None = None, brain_endpoint: str | None = None):
        """Initialize WorkerService.

        Args:
            temporal_host: Temporal server host (default: localhost:7233)
            brain_endpoint: Brain gRPC endpoint (default: brain.contextunity.ts.net:50051)
        """
        cfg = get_config()
        self.brain_endpoint = brain_endpoint or cfg.brain_endpoint

        if cfg.worker_engine == "huey":
            from .engines.huey_engine import HueyEngine

            self.engine = HueyEngine()
            logger.info("Worker is using HueyEngine (Local Mode)")
        else:
            from .engines.temporal_engine import TemporalEngine

            self.temporal_host = temporal_host or cfg.temporal_host
            self.engine = TemporalEngine(self.temporal_host)
            logger.info("Worker is using TemporalEngine (Production Mode)")

    async def StartWorkflow(self, request, context):
        """Start a durable workflow via Temporal or Huey.

        Request payload:
            - workflow_type: "harvest", "gardener", "sync", etc.
            - tenant_id: Tenant identifier
            - Additional workflow-specific parameters

        Response payload:
            - workflow_id: Temporal workflow ID
            - run_id: Temporal run ID
            - status: "started"
        """
        try:
            unit = parse_unit(request)
            token = _get_verified_token(context)

            tenant_id = unit.payload.get("tenant_id", "default")
            _authorize_worker(
                context,
                token,
                permission="worker:execute",
                rpc_name="StartWorkflow",
                tenant_id=tenant_id,
            )

            # Unit-level scope check
            if unit.security and not token.can_write(unit.security):
                context.abort(
                    grpc.StatusCode.PERMISSION_DENIED,
                    f"Token cannot write to SecurityScopes: {unit.security.write}",
                )

            workflow_type = unit.payload.get("workflow_type")
            task_queue = unit.payload.get("task_queue", f"{tenant_id}-tasks")
            workflow_args = unit.payload.get("args", [])

            # Delegate to selected engine
            response_payload = await self.engine.start_workflow(
                unit=unit,
                workflow_type=workflow_type,
                tenant_id=tenant_id,
                task_queue=task_queue,
                workflow_args=workflow_args,
            )

            # Create response unit
            response_unit = ContextUnit(
                payload=response_payload,
                trace_id=unit.trace_id,
            )

            if contextunit_pb2:
                return response_unit.to_protobuf(contextunit_pb2)
            return response_unit.to_protobuf()

        except Exception as e:
            logger.error(f"StartWorkflow failed: {e}", exc_info=True)
            from uuid import uuid4

            error_unit = ContextUnit(
                payload={
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                trace_id=unit.trace_id if "unit" in locals() else uuid4(),
            )
            if contextunit_pb2:
                return error_unit.to_protobuf(contextunit_pb2)
            return error_unit.to_protobuf()

    async def GetTaskStatus(self, request, context):
        """Get status of a running workflow/task.

        Request payload:
            - workflow_id: Temporal/Huey workflow ID

        Response payload:
            - status: "running", "completed", "failed"
            - result: Workflow result (if completed)
            - error: Error message (if failed)
        """
        try:
            unit = parse_unit(request)
            token = _get_verified_token(context)

            _authorize_worker(
                context,
                token,
                permission="worker:read",
                rpc_name="GetTaskStatus",
            )

            # Unit-level scope check
            if unit.security and not token.can_read(unit.security):
                context.abort(
                    grpc.StatusCode.PERMISSION_DENIED,
                    f"Token cannot read from SecurityScopes: {unit.security.read}",
                )

            workflow_id = unit.payload.get("workflow_id")
            if not workflow_id:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, "workflow_id is required")

            payload = await self.engine.get_task_status(workflow_id)

            response_unit = ContextUnit(
                payload=payload,
                trace_id=unit.trace_id,
            )

            if contextunit_pb2:
                return response_unit.to_protobuf(contextunit_pb2)
            return response_unit.to_protobuf()

        except Exception as e:
            logger.error(f"GetTaskStatus failed: {e}", exc_info=True)
            from uuid import uuid4

            error_unit = ContextUnit(
                payload={
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                trace_id=unit.trace_id if "unit" in locals() else uuid4(),
            )
            if contextunit_pb2:
                return error_unit.to_protobuf(contextunit_pb2)
            return error_unit.to_protobuf()

    async def RegisterSchedules(self, request, context):
        """Register project schedules into Temporal.

        Request payload:
            - project_id: Project identifier
            - tenant_id: Tenant identifier
            - schedules: List of schedule dictionaries

        Response payload:
            - status: "ok"
            - registered_count: Number of schedules registered
        """
        try:
            unit = parse_unit(request)
            token = _get_verified_token(context)

            _authorize_worker(
                context,
                token,
                permission="worker:execute",
                rpc_name="RegisterSchedules",
            )

            project_id = unit.payload.get("project_id")
            tenant_id = unit.payload.get("tenant_id")
            schedules = unit.payload.get("schedules", [])

            if not project_id or not tenant_id:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, "project_id and tenant_id are required")

            registered_count = await self.engine.register_schedules(
                project_id=project_id, tenant_id=tenant_id, schedules=schedules
            )

            response_unit = ContextUnit(
                payload={
                    "status": "ok",
                    "registered_count": registered_count,
                },
                trace_id=unit.trace_id,
            )

            if contextunit_pb2:
                return response_unit.to_protobuf(contextunit_pb2)
            return response_unit.to_protobuf()

        except Exception as e:
            logger.error(f"RegisterSchedules failed: {e}", exc_info=True)
            from uuid import uuid4

            error_unit = ContextUnit(
                payload={
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                trace_id=unit.trace_id if "unit" in locals() else uuid4(),
            )
            if contextunit_pb2:
                return error_unit.to_protobuf(contextunit_pb2)
            return error_unit.to_protobuf()

    async def ExecuteCode(self, request, context):
        """Execute a small segment of agent-generated code (sandboxed).

        Request payload:
            - code: Code to execute
            - language: "python" (default)
            - timeout: Timeout in seconds (default: 30)

        Response payload:
            - result: Execution result
            - stdout: Standard output
            - stderr: Standard error
        """
        try:
            unit = parse_unit(request)
            token = _get_verified_token(context)

            _authorize_worker(
                context,
                token,
                permission="worker:execute",
                rpc_name="ExecuteCode",
            )

            # Unit-level scope check
            if unit.security and not token.can_write(unit.security):
                context.abort(
                    grpc.StatusCode.PERMISSION_DENIED,
                    f"Token cannot write to SecurityScopes: {unit.security.write}",
                )

            code = unit.payload.get("code")
            if not code:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, "code is required")

            # TODO: Implement sandboxed code execution
            # For now, return placeholder
            logger.warning("ExecuteCode not yet implemented, returning placeholder")

            response_unit = ContextUnit(
                payload={
                    "result": None,
                    "stdout": "",
                    "stderr": "ExecuteCode not yet implemented",
                },
                trace_id=unit.trace_id,
            )

            if contextunit_pb2:
                return response_unit.to_protobuf(contextunit_pb2)
            return response_unit.to_protobuf()

        except Exception as e:
            logger.error(f"ExecuteCode failed: {e}", exc_info=True)
            from uuid import uuid4

            error_unit = ContextUnit(
                payload={
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                trace_id=unit.trace_id if "unit" in locals() else uuid4(),
            )
            if contextunit_pb2:
                return error_unit.to_protobuf(contextunit_pb2)
            return error_unit.to_protobuf()


__all__ = ["WorkerService"]
