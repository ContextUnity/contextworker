"""WorkerService - gRPC service for contextunity.worker."""

from __future__ import annotations

from contextunity.core import (
    contextunit_pb2,
    get_contextunit_logger,
    worker_pb2_grpc,
)
from contextunity.core.exceptions import SecurityError
from contextunity.core.sdk.payload import (
    get_dict_list,
    get_object_list,
    get_optional_str,
    get_required_str,
)
from contextunity.core.tokens import ContextToken
from contextunity.worker.decorators import grpc_error_handler
from contextunity.worker.helpers import make_response, parse_unit
from grpc.aio import ServicerContext

from .config import get_config
from .engines.base import BaseTaskEngine

logger = get_contextunit_logger(__name__)

ContextUnitProto = contextunit_pb2.ContextUnit


def _get_verified_token(_context: ServicerContext[ContextUnitProto, ContextUnitProto]) -> ContextToken:
    """Get the verified token from VerifiedAuthContext (set by interceptor).

    Always fail-closed: no token = SecurityError → UNAUTHENTICATED.

    Returns:
        ContextToken — verified and non-expired.

    Raises:
        SecurityError: on missing/expired token (mapped to UNAUTHENTICATED by grpc_error_handler).
    """
    from contextunity.core.authz.context import get_auth_context

    auth_ctx = get_auth_context()
    if auth_ctx is not None:
        return auth_ctx.token

    raise SecurityError(
        "No verified auth context found — fail-closed security enforced",
        code="UNAUTHENTICATED",
    )


def _resolve_tenant_id(
    _context: ServicerContext[ContextUnitProto, ContextUnitProto],
    token: ContextToken,
    payload_tenant_id: str | None,
) -> str:
    """Derive the canonical tenant_id from the token (SPOT).

    The ``ContextToken`` is the single source of truth. ``payload_tenant_id``
    is a legacy/back-compat field: if provided, it MUST match the token's
    ``allowed_tenants`` — otherwise the RPC is rejected.

    Args:
        _context: gRPC servicer context (reserved for future abort hooks).
        token: Verified ContextToken.
        payload_tenant_id: Optional legacy tenant_id from the payload.

    Returns:
        Canonical tenant_id string.
    """
    allowed = tuple(getattr(token, "allowed_tenants", ()) or ())

    if payload_tenant_id:
        if allowed and payload_tenant_id not in allowed:
            raise SecurityError(
                f"Payload tenant_id '{payload_tenant_id}' not in token allowed_tenants={allowed} (SPOT violation)",
            )
        return payload_tenant_id

    if allowed:
        return allowed[0]

    raise SecurityError(
        "Cannot resolve tenant_id: token has no allowed_tenants and payload did not supply one.",
    )


def _authorize_worker(
    _context: ServicerContext[ContextUnitProto, ContextUnitProto],
    token: ContextToken,
    *,
    permission: str,
    rpc_name: str,
    tenant_id: str | None = None,
) -> None:
    """Run canonical authorization check for a Worker RPC.

    Args:
        _context: gRPC servicer context (reserved for future abort hooks).
        token: Verified ContextToken.
        permission: Required permission string.
        rpc_name: RPC method name (for audit).
        tenant_id: Target tenant to check binding (optional).

    Raises:
        SecurityError: On authorization failure.
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
        raise SecurityError(decision.reason)


class WorkerService(worker_pb2_grpc.WorkerServiceServicer):
    """gRPC service for contextunity.worker.

    Handles workflow triggers, status queries, schedule registration, and code
    execution requests via the ContextUnit protocol.

    Authorization is enforced at two layers:
    1. ``WorkerPermissionInterceptor`` — RPC-level permission check
    2. Handler-level — tenant binding and resource-level checks
    """

    brain_endpoint: str
    engine: BaseTaskEngine
    temporal_host: str | None

    def __init__(
        self,
        temporal_host: str | None = None,
        brain_endpoint: str | None = None,
        engine_override: BaseTaskEngine | None = None,
    ):
        """Initialize WorkerService.

        Args:
            temporal_host: Temporal server host (default: localhost:7233)
            brain_endpoint: Brain gRPC endpoint override. When omitted, uses
                the resolved Worker configuration value.
            engine_override: Optional explicit engine instance (used for Local Supervisor)
        """
        cfg = get_config()
        self.brain_endpoint = brain_endpoint or cfg.brain_endpoint
        self.temporal_host = None

        if engine_override is not None:
            self.engine = engine_override
            logger.info("Worker is using an injected engine override (Local Supervisor)")
        elif cfg.worker_engine == "huey":
            from .engines.huey_engine import HueyEngine

            self.engine = HueyEngine()
            logger.info("Worker is using HueyEngine (Local Mode)")
        else:
            from .engines.temporal_engine import TemporalEngine

            self.temporal_host = temporal_host or cfg.temporal_host
            self.engine = TemporalEngine(self.temporal_host)
            logger.info("Worker is using TemporalEngine (Production Mode)")

    @grpc_error_handler
    async def StartWorkflow(
        self,
        request: ContextUnitProto,
        context: ServicerContext[ContextUnitProto, ContextUnitProto],
    ) -> ContextUnitProto:
        """Start a durable workflow via Temporal or Huey."""
        unit = parse_unit(request)
        token = _get_verified_token(context)

        tenant_id = _resolve_tenant_id(
            context,
            token,
            get_optional_str(unit.payload, "tenant_id"),
        )
        _authorize_worker(
            context,
            token,
            permission="worker:execute",
            rpc_name="StartWorkflow",
            tenant_id=tenant_id,
        )

        if unit.security and not token.can_write(unit.security):
            raise SecurityError(
                f"Token cannot write to SecurityScopes: {unit.security.write}",
            )

        workflow_type = get_required_str(unit.payload, "workflow_type")
        task_queue_raw = unit.payload.get("task_queue")
        task_queue = task_queue_raw if isinstance(task_queue_raw, str) else f"{tenant_id}-tasks"
        workflow_args = get_object_list(unit.payload, "args")

        response_payload = await self.engine.start_workflow(
            unit=unit,
            workflow_type=workflow_type,
            tenant_id=tenant_id,
            task_queue=task_queue,
            workflow_args=workflow_args,
        )

        return make_response(
            payload=response_payload,
            parent_unit=unit,
        )

    @grpc_error_handler
    async def GetTaskStatus(
        self,
        request: ContextUnitProto,
        context: ServicerContext[ContextUnitProto, ContextUnitProto],
    ) -> ContextUnitProto:
        """Get status of a running workflow/task."""
        unit = parse_unit(request)
        token = _get_verified_token(context)
        tenant_id = _resolve_tenant_id(
            context,
            token,
            get_optional_str(unit.payload, "tenant_id"),
        )

        _authorize_worker(
            context,
            token,
            permission="worker:read",
            rpc_name="GetTaskStatus",
            tenant_id=tenant_id,
        )

        if unit.security and not token.can_read(unit.security):
            raise SecurityError(
                f"Token cannot read from SecurityScopes: {unit.security.read}",
            )

        workflow_id = get_required_str(unit.payload, "workflow_id")
        payload = await self.engine.get_task_status(workflow_id)

        return make_response(
            payload=payload,
            parent_unit=unit,
        )

    @grpc_error_handler
    async def RegisterSchedules(
        self,
        request: ContextUnitProto,
        context: ServicerContext[ContextUnitProto, ContextUnitProto],
    ) -> ContextUnitProto:
        """Register project schedules into Temporal."""
        unit = parse_unit(request)
        token = _get_verified_token(context)

        tenant_id = _resolve_tenant_id(
            context,
            token,
            get_optional_str(unit.payload, "tenant_id"),
        )
        _authorize_worker(
            context,
            token,
            permission="worker:execute",
            rpc_name="RegisterSchedules",
            tenant_id=tenant_id,
        )

        project_id = get_required_str(unit.payload, "project_id")
        schedules = get_dict_list(unit.payload, "schedules")

        registered_count = await self.engine.register_schedules(
            project_id=project_id,
            tenant_id=tenant_id,
            schedules=schedules,
        )

        return make_response(
            payload={
                "status": "ok",
                "registered_count": registered_count,
            },
            parent_unit=unit,
        )

    @grpc_error_handler
    async def ExecuteCode(
        self,
        request: ContextUnitProto,
        context: ServicerContext[ContextUnitProto, ContextUnitProto],
    ) -> ContextUnitProto:
        """Execute a small segment of agent-generated code (sandboxed)."""
        unit = parse_unit(request)
        token = _get_verified_token(context)

        _authorize_worker(
            context,
            token,
            permission="worker:execute",
            rpc_name="ExecuteCode",
        )

        if unit.security and not token.can_write(unit.security):
            raise SecurityError(
                f"Token cannot write to SecurityScopes: {unit.security.write}",
            )

        _ = get_required_str(unit.payload, "code")

        logger.warning("ExecuteCode not yet implemented, returning placeholder")

        return make_response(
            payload={
                "result": None,
                "stdout": "",
                "stderr": "ExecuteCode not yet implemented",
            },
            parent_unit=unit,
        )


__all__ = ["WorkerService"]
