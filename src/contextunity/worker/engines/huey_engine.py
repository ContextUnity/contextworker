"""Huey task execution engine."""

import logging
import uuid
from typing import Any

from contextunity.core import ContextUnit
from contextunity.core.config import get_core_config

from .base import BaseTaskEngine

logger = logging.getLogger(__name__)

# Lazy initialization of the Huey instance
_huey_instance = None


def get_huey():
    """Get or create singleton Huey instance."""
    global _huey_instance
    if _huey_instance is None:
        from huey import RedisHuey

        core_cfg = get_core_config()
        if not core_cfg.redis_url:
            raise ValueError("REDIS_URL must be set to use Huey task engine.")

        # Import URL parser
        from urllib.parse import urlparse

        parsed_url = urlparse(core_cfg.redis_url)
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
    """Local, lightweight task engine backed by Huey (Redis)."""

    async def start_workflow(
        self,
        unit: ContextUnit,
        workflow_type: str,
        tenant_id: str,
        task_queue: str,
        workflow_args: list[Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Enqueue local execution of a task."""

        workflow_id = f"{workflow_type}-{unit.unit_id}-{uuid.uuid4().hex[:8]}"

        # Since Huey runs Python functions directly, and ContextUnity workflows
        # are currently tied to Temporal classes (like HarvesterImportWorkflow.run),
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

    async def get_task_status(self, workflow_id: str) -> dict[str, Any]:
        """Mock behavior for local Huey mode."""
        # Because we're simulating Temporal structure with Huey, we just mark it as completed
        # or query Huey's task result store if fully implemented.
        return {
            "workflow_id": workflow_id,
            "status": "completed",
            "result": {"message": "Simulated local Huey completion"},
        }

    async def register_schedules(self, project_id: str, tenant_id: str, schedules: list[dict[str, Any]]) -> int:
        """Mock register schedules for Huey."""
        logger.info(f"[Huey Local] Registered {len(schedules)} schedules for project {project_id}.")
        return len(schedules)
