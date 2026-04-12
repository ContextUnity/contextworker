"""Temporal task execution engine."""

import logging
from typing import Any

from contextunity.core import ContextUnit
from contextunity.core.exceptions import SecurityError
from contextunity.core.security import validate_safe_url

from .base import BaseTaskEngine

logger = logging.getLogger(__name__)


class TemporalEngine(BaseTaskEngine):
    """Task engine backed by Temporal.io (Production standard)."""

    def __init__(self, temporal_host: str):
        self.temporal_host = temporal_host
        self._client = None

    async def _get_client(self):
        """Get or create Temporal client."""
        if self._client is None:
            from temporalio.client import Client

            self._client = await Client.connect(self.temporal_host)
        return self._client

    async def start_workflow(
        self,
        unit: ContextUnit,
        workflow_type: str,
        tenant_id: str,
        task_queue: str,
        workflow_args: list[Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Start a durable workflow in Temporal."""
        client = await self._get_client()

        if workflow_type == "harvest":
            from contextunity.worker.workflows import HarvesterImportWorkflow

            raw_url = unit.payload.get("url")
            if not raw_url:
                raise ValueError("url is required for harvest workflow")

            try:
                url = validate_safe_url(raw_url, allow_local=False)
            except SecurityError as e:
                raise ValueError(str(e))

            handle = await client.start_workflow(
                HarvesterImportWorkflow.run,
                url,
                id=f"harvest-{unit.unit_id}",
                task_queue="harvester-tasks",
            )
        else:
            logger.info(f"Starting generic workflow '{workflow_type}' on queue '{task_queue}' via Temporal")
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

    async def get_task_status(self, workflow_id: str) -> dict[str, Any]:
        """Get workflow status from Temporal."""
        client = await self._get_client()

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

        payload: dict[str, Any] = {
            "workflow_id": workflow_id,
            "status": status,
        }

        if status == "completed":
            try:
                result = await handle.result()
                payload["result"] = result
            except Exception as e:
                logger.warning(f"Failed to get workflow result: {e}")

        if status == "failed":
            payload["error"] = "Workflow failed"

        return payload

    async def register_schedules(self, project_id: str, tenant_id: str, schedules: list[dict[str, Any]]) -> int:
        """Register schedules in Temporal."""
        client = await self._get_client()
        from contextunity.worker.schedules import ScheduleConfig, create_schedule

        registered_count = 0
        for sched_data in schedules:
            try:
                config = ScheduleConfig(**sched_data)
                await create_schedule(client, config, tenant_id=tenant_id)
                registered_count += 1
            except Exception as e:
                logger.error(f"Failed to register schedule {sched_data.get('id')}: {e}")

        return registered_count
