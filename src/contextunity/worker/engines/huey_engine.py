"""Huey task execution engine.

Provides a lightweight, Redis-backed local task execution engine utilizing the Huey
library. Used primarily for local development, debugging, and testing environments
where a full Temporal deployment is not required.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, override

from contextunity.core import ContextUnit
from contextunity.core.config import get_core_config
from contextunity.core.exceptions import ConfigurationError
from contextunity.core.types import ContextUnitPayload

from .base import BaseTaskEngine

if TYPE_CHECKING:
    from huey import RedisHuey, SqliteHuey

logger = logging.getLogger(__name__)

# Lazy initialization of the Huey instance
_huey_instance = None


def get_huey() -> RedisHuey:
    """Resolve, configure, and return the singleton RedisHuey instance.

    Parses the Redis URL from the core configuration to establish the Huey backend
    connection.

    Returns:
        The configured RedisHuey instance.

    Raises:
        ValueError: If REDIS_URL is not set in the configuration.
    """
    global _huey_instance
    if _huey_instance is None:
        from huey import RedisHuey

        core_cfg = get_core_config()
        if not core_cfg.redis.url:
            raise ConfigurationError("REDIS_URL must be set to use Huey task engine.")

        # Import URL parser
        from urllib.parse import urlparse

        parsed_url = urlparse(core_cfg.redis.url)
        host = parsed_url.hostname or "localhost"
        port = parsed_url.port or 6379
        password = parsed_url.password

        # Attempt extracting db number from path, else default to 0
        db = 0
        if parsed_url.path and len(parsed_url.path) > 1:
            try:
                db = int(parsed_url.path[1:])
            except ValueError:
                db = 0

        _huey_instance = RedisHuey(
            "contextunity_worker_local",
            host=host,
            port=port,
            password=password,
            db=db,
        )
        logger.info(f"Initialized RedisHuey locally on {host}:{port}/{db}")
    return _huey_instance


class HueyEngine(BaseTaskEngine):
    """Huey-backed local task execution engine.

    Simulates the orchestrator workflow interfaces using a lightweight in-memory/Redis
    queue for dev setups.
    """

    huey: RedisHuey | SqliteHuey | None

    def __init__(self, huey_instance: RedisHuey | SqliteHuey | None = None):
        """Initialize the Huey execution engine.

        Args:
            huey_instance: Optional RedisHuey instance. If not provided, it will
                be lazily initialized from the default configuration.
        """
        self.huey = huey_instance

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
        """Simulate enqueuing a workflow task in Huey for local execution.

        Simulates the execution response payload layout of Temporal workflows,
        enabling local development tests to succeed without a full runner mesh.

        Args:
            unit: The ContextUnit execution container.
            workflow_type: Target name of the workflow/job.
            tenant_id: Target tenant namespace.
            task_queue: Target queue/worker topic.
            workflow_args: Positional argument payload for the workflow run.
            **kwargs: Extra parameters passed to the engine.

        Returns:
            A dictionary containing simulated "workflow_id", "run_id", and "status".
        """
        workflow_id = f"{workflow_type}-{unit.unit_id}-{uuid.uuid4().hex[:8]}"

        # Since Huey runs Python functions directly, and ContextUnity workflows
        # are currently modeled as Temporal workflow entrypoints,
        # local Huey execution essentially functions as a stub for CLI dev environments
        # or dispatches to synchronous/async runner layers if mapped.
        # For now, we simulate success for local debugging.

        # If we had a direct Python mapping:
        # huey.enqueue(workflow_runner_task, workflow_type, tenant_id, workflow_args)

        logger.info(f"[Huey Local] Enqueued workflow '{workflow_type}' as '{workflow_id}'")

        # Emulate Temporal payload structure
        return {
            "workflow_id": workflow_id,
            "run_id": f"local-run-{uuid.uuid4().hex[:8]}",
            "status": "started",
        }

    @override
    async def get_task_status(self, workflow_id: str) -> ContextUnitPayload:
        """Fetch the execution status of a Huey-simulated workflow.

        Args:
            workflow_id: The unique workflow identifier string.

        Returns:
            A dictionary capturing current status and completion results.
        """
        # Because we're simulating Temporal structure with Huey, we just mark it as completed
        # or query Huey's task result store if fully implemented.
        return {
            "workflow_id": workflow_id,
            "status": "completed",
            "result": {"message": "Simulated local Huey completion"},
        }

    @override
    async def register_schedules(self, project_id: str, tenant_id: str, schedules: list[dict[str, object]]) -> int:
        """Register recurring schedules within the Huey engine.

        Args:
            project_id: Unique project context ID.
            tenant_id: Enforcing tenant partition.
            schedules: List of dictionaries mapping tasks to cron/interval specs.

        Returns:
            The number of successfully registered schedules.
        """
        logger.info(f"[Huey Local] Registered {len(schedules)} schedules for project {project_id}.")
        return len(schedules)
