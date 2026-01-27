"""
Harvester Agent - Stock Import Orchestrator.

Uses Temporal workflows for durable execution of:
1. Fetch vendor data (HTTP/FTP)
2. Parse payload (XLS/XML/JSON)
3. Stage to Commerce DB

Note: This agent is Temporal-based, not polling-based.
See workflows.py for workflow definitions.
"""

import logging
from ..registry import register, BaseAgent

logger = logging.getLogger(__name__)


@register("harvester")
class HarvesterAgent(BaseAgent):
    """
    Temporal worker for harvester workflows.

    Unlike polling agents, this runs as a Temporal worker
    that listens for workflow tasks from the Temporal server.
    """

    name = "harvester"

    def run(self):
        """Start Temporal worker."""
        logger.info("Harvester agent starting Temporal worker...")

        # Import here to avoid circular dependencies
        from ..worker import run_temporal_worker

        # This blocks until worker is stopped
        run_temporal_worker(task_queue="harvester-tasks")
