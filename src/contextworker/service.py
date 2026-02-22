"""WorkerService - gRPC service for ContextWorker."""

from __future__ import annotations

import grpc

# Import generated protobuf stubs — fail-closed: service MUST NOT start
# without gRPC contracts (Secure by Default).
from contextcore import (
    ContextUnit,
    context_unit_pb2,
    extract_token_from_grpc_metadata,
    get_context_unit_logger,
    worker_pb2_grpc,
)
from contextcore.exceptions import SecurityError
from contextcore.security import validate_safe_url

from .config import get_config
from .subagents.executor import SubAgentExecutor
from .subagents.isolation import IsolationContext

logger = get_context_unit_logger(__name__)


def parse_unit(request) -> ContextUnit:
    """Parse protobuf request to ContextUnit."""
    return ContextUnit.from_protobuf(request)


class WorkerService(worker_pb2_grpc.WorkerServiceServicer):
    """gRPC service for ContextWorker.

    Handles workflow triggers and sub-agent execution via ContextUnit protocol.
    """

    def __init__(self, temporal_host: str | None = None, brain_endpoint: str | None = None):
        """Initialize WorkerService.

        Args:
            temporal_host: Temporal server host (default: localhost:7233)
            brain_endpoint: Brain gRPC endpoint (default: brain.contextunity.ts.net:50051)
        """
        cfg = get_config()
        self.temporal_host = temporal_host or cfg.temporal_host
        self.brain_endpoint = brain_endpoint or cfg.brain_endpoint
        self._client = None

        from .core.brain_token import get_brain_service_token

        self._executor = SubAgentExecutor(
            brain_endpoint=self.brain_endpoint,
            token=get_brain_service_token(),
        )

    async def get_client(self):
        """Get or create Temporal client."""
        if self._client is None:
            from temporalio.client import Client

            self._client = await Client.connect(self.temporal_host)
        return self._client

    async def StartWorkflow(self, request, context):
        """Start a durable workflow via Temporal.

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
            token = extract_token_from_grpc_metadata(context)

            # Validate token — fail-closed: no token = deny when security enabled
            if token:
                if token.is_expired():
                    context.abort(grpc.StatusCode.UNAUTHENTICATED, "Token expired")
                if not token.has_permission("worker:execute"):
                    context.abort(
                        grpc.StatusCode.PERMISSION_DENIED,
                        f"Token lacks 'worker:execute' permission. Permissions: {token.permissions}",
                    )
                if unit.security and not token.can_write(unit.security):
                    context.abort(
                        grpc.StatusCode.PERMISSION_DENIED,
                        f"Token cannot write to SecurityScopes: {unit.security.write}",
                    )
            else:
                # Fail-closed: no token at all — reject when security enabled
                from contextcore.config import get_core_config

                config = get_core_config()
                if config.security.enabled:
                    context.abort(
                        grpc.StatusCode.UNAUTHENTICATED,
                        "No ContextToken provided — fail-closed (security enabled)",
                    )

            workflow_type = unit.payload.get("workflow_type")
            tenant_id = unit.payload.get("tenant_id", "default")

            # Validate tenant access if token is present
            if token and not token.can_access_tenant(tenant_id):
                context.abort(
                    grpc.StatusCode.PERMISSION_DENIED,
                    f"Token not authorized for tenant '{tenant_id}'. "
                    f"Allowed tenants: {list(token.allowed_tenants) or 'none'}",
                )

            # Get Temporal client
            client = await self.get_client()

            if workflow_type == "harvest":
                from contextworker.workflows import HarvesterImportWorkflow

                raw_url = unit.payload.get("url")
                if not raw_url:
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT, "url is required for harvest workflow")

                try:
                    url = validate_safe_url(raw_url, allow_local=False)
                except SecurityError as e:
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))

                handle = await client.start_workflow(
                    HarvesterImportWorkflow.run,
                    url,
                    id=f"harvest-{unit.unit_id}",
                    task_queue="harvester-tasks",
                )
            elif workflow_type == "subagent":
                subagent_id = unit.payload.get("subagent_id")
                task = unit.payload.get("task") or {}
                agent_type = unit.payload.get("agent_type", "task_executor")
                config = unit.payload.get("config") or {}
                isolation_context_data = unit.payload.get("isolation_context") or {}
                isolation_context = IsolationContext.from_dict(isolation_context_data)

                if not subagent_id:
                    context.abort(
                        grpc.StatusCode.INVALID_ARGUMENT,
                        "subagent_id is required for workflow_type=subagent",
                    )

                # Execute sub-agent immediately via executor path.
                # Temporal orchestration for sub-agents can be added later.
                execution_result = await self._executor.execute_subagent(
                    subagent_id=subagent_id,
                    task=task,
                    agent_type=agent_type,
                    isolation_context=isolation_context,
                    config=config,
                    unit=unit,
                    token=token,
                )

                response_unit = ContextUnit(
                    payload={
                        "workflow_id": subagent_id,
                        "run_id": None,
                        "status": execution_result.get("status", "completed"),
                        "result": execution_result.get("result"),
                        "error": execution_result.get("error"),
                    },
                    trace_id=unit.trace_id,
                    provenance=list(unit.provenance) + ["worker:start_workflow:subagent"],
                )

                if context_unit_pb2:
                    return response_unit.to_protobuf(context_unit_pb2)
                return response_unit.to_protobuf()
            else:
                # Generic workflow - use workflow_type as workflow class name
                logger.warning(f"Unknown workflow type: {workflow_type}, creating placeholder")
                # For now, return error for unknown types
                error_unit = ContextUnit(
                    payload={
                        "error": f"Unknown workflow type: {workflow_type}",
                        "workflow_id": None,
                    },
                    trace_id=unit.trace_id,
                    provenance=list(unit.provenance) + ["worker:start_workflow:error"],
                )
                if context_unit_pb2:
                    return error_unit.to_protobuf(context_unit_pb2)
                return error_unit.to_protobuf()

            # Create response unit
            response_unit = ContextUnit(
                payload={
                    "workflow_id": handle.id,
                    "run_id": handle.result_run_id,
                    "status": "started",
                },
                trace_id=unit.trace_id,
                provenance=list(unit.provenance) + ["worker:start_workflow"],
            )

            if context_unit_pb2:
                return response_unit.to_protobuf(context_unit_pb2)
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
                provenance=(list(unit.provenance) + ["worker:start_workflow:error"])
                if "unit" in locals()
                else ["worker:start_workflow:error"],
            )
            if context_unit_pb2:
                return error_unit.to_protobuf(context_unit_pb2)
            return error_unit.to_protobuf()

    async def GetTaskStatus(self, request, context):
        """Get status of a running workflow/task.

        Request payload:
            - workflow_id: Temporal workflow ID

        Response payload:
            - status: "running", "completed", "failed"
            - result: Workflow result (if completed)
            - error: Error message (if failed)
        """
        try:
            unit = parse_unit(request)
            token = extract_token_from_grpc_metadata(context)

            # Validate token — fail-closed: no token = deny when security enabled
            if token:
                if token.is_expired():
                    context.abort(grpc.StatusCode.UNAUTHENTICATED, "Token expired")
                if not token.has_permission("worker:read"):
                    context.abort(
                        grpc.StatusCode.PERMISSION_DENIED,
                        f"Token lacks 'worker:read' permission. Permissions: {token.permissions}",
                    )
                if unit.security and not token.can_read(unit.security):
                    context.abort(
                        grpc.StatusCode.PERMISSION_DENIED,
                        f"Token cannot read from SecurityScopes: {unit.security.read}",
                    )
            else:
                from contextcore.config import get_core_config

                config = get_core_config()
                if config.security.enabled:
                    context.abort(
                        grpc.StatusCode.UNAUTHENTICATED,
                        "No ContextToken provided — fail-closed (security enabled)",
                    )

            workflow_id = unit.payload.get("workflow_id")
            if not workflow_id:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, "workflow_id is required")

            # Get Temporal client
            client = await self.get_client()

            # Get workflow handle
            handle = client.get_workflow_handle(workflow_id)

            # Get workflow status
            description = await handle.describe()

            status_map = {
                "RUNNING": "running",
                "COMPLETED": "completed",
                "FAILED": "failed",
                "CANCELLED": "cancelled",
                "TERMINATED": "terminated",
                "CONTINUED_AS_NEW": "running",
                "TIMED_OUT": "failed",
            }

            status = status_map.get(description.status.name, "unknown")

            payload = {
                "workflow_id": workflow_id,
                "status": status,
            }

            # Get result if completed
            if status == "completed":
                try:
                    result = await handle.result()
                    payload["result"] = result
                except Exception as e:
                    logger.warning(f"Failed to get workflow result: {e}")

            # Get error if failed
            if status == "failed":
                try:
                    # Try to get failure info
                    payload["error"] = "Workflow failed"
                except Exception:
                    pass

            response_unit = ContextUnit(
                payload=payload,
                trace_id=unit.trace_id,
                provenance=list(unit.provenance) + ["worker:get_task_status"],
            )

            if context_unit_pb2:
                return response_unit.to_protobuf(context_unit_pb2)
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
                provenance=(list(unit.provenance) + ["worker:get_task_status:error"])
                if "unit" in locals()
                else ["worker:get_task_status:error"],
            )
            if context_unit_pb2:
                return error_unit.to_protobuf(context_unit_pb2)
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
            token = extract_token_from_grpc_metadata(context)

            # Validate token — fail-closed: no token = deny when security enabled
            if token:
                if token.is_expired():
                    context.abort(grpc.StatusCode.UNAUTHENTICATED, "Token expired")
                if not token.has_permission("worker:execute"):
                    context.abort(
                        grpc.StatusCode.PERMISSION_DENIED,
                        f"Token lacks 'worker:execute' permission. Permissions: {token.permissions}",
                    )
                if unit.security and not token.can_write(unit.security):
                    context.abort(
                        grpc.StatusCode.PERMISSION_DENIED,
                        f"Token cannot write to SecurityScopes: {unit.security.write}",
                    )
            else:
                from contextcore.config import get_core_config

                config = get_core_config()
                if config.security.enabled:
                    context.abort(
                        grpc.StatusCode.UNAUTHENTICATED,
                        "No ContextToken provided — fail-closed (security enabled)",
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
                provenance=list(unit.provenance) + ["worker:execute_code:not_implemented"],
            )

            if context_unit_pb2:
                return response_unit.to_protobuf(context_unit_pb2)
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
                provenance=(list(unit.provenance) + ["worker:execute_code:error"])
                if "unit" in locals()
                else ["worker:execute_code:error"],
            )
            if context_unit_pb2:
                return error_unit.to_protobuf(context_unit_pb2)
            return error_unit.to_protobuf()


__all__ = ["WorkerService"]
