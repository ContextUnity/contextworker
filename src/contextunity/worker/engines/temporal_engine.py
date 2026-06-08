"""Temporal task execution engine."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from contextunity.core import ContextUnit, get_contextunit_logger
from contextunity.core.types import ContextUnitPayload

from .base import BaseTaskEngine

if TYPE_CHECKING:
    from temporalio.client import Client

logger = get_contextunit_logger(__name__)


class TemporalEngine(BaseTaskEngine):
    """Task engine backed by Temporal.io (Production standard)."""

    temporal_host: str
    _client: Client | None

    def __init__(self, temporal_host: str) -> None:
        """Initialize the Temporal.io execution engine."""
        self.temporal_host = temporal_host
        self._client = None

    async def _get_client(self) -> Client:
        """Get or create Temporal client."""
        if self._client is None:
            from temporalio.client import Client

            self._client = await Client.connect(self.temporal_host)
        return self._client

    @override
    async def start_workflow(
        self,
        unit: ContextUnit,
        workflow_type: str,
        tenant_id: str,
        task_queue: str,
        workflow_args: list[object],
        **kwargs: object,
    ) -> ContextUnitPayload:
        """Start a durable workflow in Temporal."""
        _ = tenant_id, kwargs
        client = await self._get_client()

        logger.info("Starting workflow '%s' on queue '%s' via Temporal", workflow_type, task_queue)
        handle = await client.start_workflow(
            workflow_type,
            args=workflow_args,
            id=f"{workflow_type}-{unit.unit_id}",
            task_queue=task_queue,
        )

        return {
            "workflow_id": handle.id,
            "run_id": handle.result_run_id,
            "status": "started",
        }

    @override
    async def get_task_status(self, workflow_id: str) -> ContextUnitPayload:
        """Get workflow status from Temporal."""
        client = await self._get_client()
        handle = client.get_workflow_handle(workflow_id)
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

        raw_status = description.status
        status = status_map.get(raw_status.name if raw_status else "", "unknown")

        payload: ContextUnitPayload = {
            "workflow_id": workflow_id,
            "status": status,
        }

        if status == "completed":
            try:
                import json

                payload["result"] = json.dumps(await handle.result(), default=str)
            except Exception as exc:  # graceful-degrade: status still returned without result
                logger.warning("Failed to get workflow result: %s", exc)

        if status == "failed":
            payload["error"] = "Workflow failed"

        return payload

    @override
    async def register_schedules(
        self,
        project_id: str,
        tenant_id: str,
        schedules: list[dict[str, object]],
    ) -> int:
        """Register schedules in Temporal."""
        _ = project_id, tenant_id
        client = await self._get_client()
        from contextunity.worker.schedules import create_schedule, schedule_config_from_wire

        registered_count = 0
        for sched_data in schedules:
            try:
                config = schedule_config_from_wire(sched_data)
                _ = await create_schedule(
                    client,
                    schedule_id=config.schedule_id,
                    workflow=config.workflow_name,
                    task_queue=config.task_queue,
                    cron=config.cron,
                    args=config.args,
                )
                registered_count += 1
            except Exception as exc:
                sched_id = sched_data.get("id")
                logger.error("Failed to register schedule %s: %s", sched_id, exc)

        return registered_count
