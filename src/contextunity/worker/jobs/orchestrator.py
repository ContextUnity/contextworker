"""Durable orchestration workflows for contextunity.worker."""

from __future__ import annotations

import logging
from datetime import timedelta
from uuid import uuid4

from contextunity.core.sdk import FederatedToolCallContext, ToolRegistry
from contextunity.core.sdk.clients.router import RouterClient
from contextunity.core.sdk.payload import normalize_tool_result
from contextunity.core.sdk.types import ToolPayload, ToolResult
from contextunity.core.types import ContextUnitPayload
from contextunity.worker.core.registry import WorkerRegistry
from temporalio import activity, workflow


@activity.defn(name="contextunity.worker.execute_federated_tool")
async def execute_federated_tool(
    tool_name: str,
    args: ToolPayload,
    tenant_id: str,
) -> ToolResult:
    """Execute a registered tool inside the Worker runtime for one tenant."""
    activity_logger = logging.getLogger("temporal.activity")
    activity_logger.info("Executing federated tool '%s' for tenant '%s'", tool_name, tenant_id)

    auth_ctx = FederatedToolCallContext(
        project_id=tenant_id,
        tool_name=tool_name,
        request_id=str(uuid4())[:8],
        caller_tenant=tenant_id,
        user_id=None,
    )

    try:
        result = await ToolRegistry.execute(tool_name=tool_name, args=args or {}, auth_ctx=auth_ctx)
        activity_logger.info("Successfully executed tool '%s'", tool_name)
        return normalize_tool_result(result)
    except Exception as exc:
        activity_logger.error("Failed tool execution '%s': %s", tool_name, exc)
        raise


@activity.defn(name="contextunity.worker.execute_router_graph")
async def execute_router_graph(
    graph_name: str,
    payload: ContextUnitPayload,
    tenant_id: str,
) -> ContextUnitPayload:
    """Execute a compiled Router graph for one tenant."""
    activity_logger = logging.getLogger("temporal.activity")
    activity_logger.info("Executing router graph '%s' for tenant '%s'", graph_name, tenant_id)

    router = RouterClient()
    try:
        response = await router.execute_agent(graph_name=graph_name, payload=payload)
        activity_logger.info("Successfully executed graph '%s'", graph_name)
        return dict(response)
    except Exception as exc:
        activity_logger.error("Failed graph execution '%s': %s", graph_name, exc)
        raise


@workflow.defn(name="ExecuteToolWorkflow")
class ExecuteToolWorkflow:
    """Temporal workflow that durably executes one registered tool call."""

    @workflow.run
    async def run(
        self,
        tool_name: str,
        tenant_id: str,
        args: ToolPayload | None = None,
    ) -> ToolResult:
        """Execute the tool execution workflow loop."""
        workflow.logger.info("Started ExecuteToolWorkflow for tool: %s (tenant: %s)", tool_name, tenant_id)

        tool_args = args or {}
        return await workflow.execute_activity(
            execute_federated_tool,
            args=[tool_name, tool_args, tenant_id],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=None,
        )


@workflow.defn(name="ExecuteGraphWorkflow")
class ExecuteGraphWorkflow:
    """Temporal workflow that durably executes one Router graph run."""

    @workflow.run
    async def run(
        self,
        graph_name: str,
        tenant_id: str,
        payload: ContextUnitPayload | None = None,
    ) -> ContextUnitPayload:
        """Execute the graph execution workflow loop."""
        workflow.logger.info("Started ExecuteGraphWorkflow for graph: %s (tenant: %s)", graph_name, tenant_id)

        graph_payload = payload or {}
        return await workflow.execute_activity(
            execute_router_graph,
            args=[graph_name, graph_payload, tenant_id],
            start_to_close_timeout=timedelta(minutes=60),
            retry_policy=None,
        )


def register_all(registry: WorkerRegistry) -> None:
    """Register orchestrator workflows and activities."""
    registry.register(
        name="orchestrator",
        queue="platform-queue",
        workflows=[ExecuteToolWorkflow, ExecuteGraphWorkflow],
        activities=[execute_federated_tool, execute_router_graph],
    )
