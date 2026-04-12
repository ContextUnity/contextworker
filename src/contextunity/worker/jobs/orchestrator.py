"""
Generic Orchestration Workflows for cu.worker.

These workflows provide platform-agnostic execution of Router Graphs and Federated Tools.
They are triggered by the schedules defined in project manifests.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict

from contextunity.core.sdk.clients.router import RouterClient
from temporalio import activity, workflow

with workflow.unsafe.imports_passed_through():
    from contextunity.worker.core.registry import WorkerRegistry


@activity.defn(name="contextunity.worker.execute_federated_tool")
async def execute_federated_tool(tool_name: str, args: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
    """Execute a federated tool generically via cu.router."""
    activity_logger = logging.getLogger("temporal.activity")
    activity_logger.info(f"Executing federated tool '{tool_name}' for tenant '{tenant_id}'")

    router = RouterClient()
    try:
        result = await router.execute_tool(tool_name=tool_name, args=args, target_project=tenant_id)
        activity_logger.info(f"Successfully executed tool '{tool_name}'")
        return result if isinstance(result, dict) else {"result": result}
    except Exception as e:
        activity_logger.error(f"Failed tool execution '{tool_name}': {str(e)}")
        raise


@workflow.defn(name="ExecuteToolWorkflow")
class ExecuteToolWorkflow:
    """Generic workflow to execute a tool (useful for cron polling)."""

    @workflow.run
    async def run(self, tool_name: str, tenant_id: str, args: Dict[str, Any] | None = None) -> Dict[str, Any]:
        workflow.logger.info(f"Started ExecuteToolWorkflow for tool: {tool_name} (tenant: {tenant_id})")

        args = args or {}
        # Execute the wrapper activity
        result = await workflow.execute_activity(
            execute_federated_tool,
            args=[tool_name, args, tenant_id],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=None,  # Do not retry indefinitely for scheduled runs
        )
        return result


@activity.defn(name="contextunity.worker.execute_router_graph")
async def execute_router_graph(graph_name: str, payload: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
    """Execute a LangGraph agent generically via cu.router."""
    activity_logger = logging.getLogger("temporal.activity")
    activity_logger.info(f"Executing router graph '{graph_name}' for tenant '{tenant_id}'")

    router = RouterClient()
    try:
        response = await router.execute_agent(agent_id=graph_name, payload=payload, tenant_id=tenant_id)
        activity_logger.info(f"Successfully executed graph '{graph_name}'")
        return response.payload if response and hasattr(response, "payload") else {}
    except Exception as e:
        activity_logger.error(f"Failed graph execution '{graph_name}': {str(e)}")
        raise


@workflow.defn(name="ExecuteGraphWorkflow")
class ExecuteGraphWorkflow:
    """Generic workflow to execute an entire router graph (useful for daily scheduled tasks)."""

    @workflow.run
    async def run(self, graph_name: str, tenant_id: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        workflow.logger.info(f"Started ExecuteGraphWorkflow for graph: {graph_name} (tenant: {tenant_id})")

        payload = payload or {}
        result = await workflow.execute_activity(
            execute_router_graph,
            args=[graph_name, payload, tenant_id],
            start_to_close_timeout=timedelta(minutes=60),  # Graphs can take a long time
            retry_policy=None,
        )
        return result


def register_all(registry: WorkerRegistry) -> None:
    """Register module items into the Worker container."""
    registry.register(
        name="orchestrator",
        queue="platform-queue",
        workflows=[ExecuteToolWorkflow, ExecuteGraphWorkflow],
        activities=[execute_federated_tool, execute_router_graph],
    )
