"""Base interface for worker execution engines."""

from __future__ import annotations

from abc import ABC, abstractmethod

from contextunity.core import ContextUnit
from contextunity.core.types import ContextUnitPayload


class BaseTaskEngine(ABC):
    """Abstract interface for task execution engines (Temporal, Huey, etc.)."""

    @abstractmethod
    async def start_workflow(
        self,
        unit: ContextUnit,
        workflow_type: str,
        tenant_id: str,
        task_queue: str,
        workflow_args: list[object],
        **kwargs: object,
    ) -> ContextUnitPayload:
        """Start a durable or background workflow.

        Returns:
            Engine-specific identifiers (e.g. workflow_id, status).
        """
        ...

    @abstractmethod
    async def get_task_status(self, workflow_id: str) -> ContextUnitPayload:
        """Get the status of a running task/workflow."""
        ...

    @abstractmethod
    async def register_schedules(
        self,
        project_id: str,
        tenant_id: str,
        schedules: list[dict[str, object]],
    ) -> int:
        """Register recurring schedules."""
        ...
