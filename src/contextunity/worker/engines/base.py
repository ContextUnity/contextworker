"""Base interface for worker execution engines."""

from abc import ABC, abstractmethod
from typing import Any

from contextunity.core import ContextUnit


class BaseTaskEngine(ABC):
    """Abstract interface for task execution engines (Temporal, Huey, etc.)."""

    @abstractmethod
    async def start_workflow(
        self,
        unit: ContextUnit,
        workflow_type: str,
        tenant_id: str,
        task_queue: str,
        workflow_args: list[Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Start a durable or background workflow.

        Returns:
            dict containing engine-specific identifiers (e.g. workflow_id, status)
        """
        pass

    @abstractmethod
    async def get_task_status(self, workflow_id: str) -> dict[str, Any]:
        """Get the status of a running task/workflow.

        Returns:
            dict containing status ("running", "completed", "failed"), result, and error.
        """
        pass

    @abstractmethod
    async def register_schedules(self, project_id: str, tenant_id: str, schedules: list[dict[str, Any]]) -> int:
        """Register recurring schedules.

        Returns:
            Number of registered schedules.
        """
        pass
