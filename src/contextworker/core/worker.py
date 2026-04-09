"""
Temporal Worker Factory.

Creates and runs Temporal workers based on registered modules.
"""

from __future__ import annotations

import asyncio
from typing import List, Optional

from contextcore import get_context_unit_logger
from temporalio.client import Client
from temporalio.worker import Worker

from .registry import get_registry

logger = get_context_unit_logger(__name__)


async def get_temporal_client(host: str = None) -> Client:
    """Get Temporal client connection (host from config if not provided)."""
    if host is None:
        from ..config import get_config

        host = get_config().temporal_host
    return await Client.connect(host)


async def create_worker(
    client: Client,
    queue: str,
    workflows: List = None,
    activities: List = None,
) -> Worker:
    """Create a Temporal worker for a specific queue."""
    return Worker(
        client,
        task_queue=queue,
        workflows=workflows or [],
        activities=activities or [],
    )


async def run_workers(
    modules: Optional[List[str]] = None,
    temporal_host: str = None,
) -> None:
    """Run Temporal workers for specified modules.

    Args:
        modules: List of module names to run (None = all enabled)
        temporal_host: Temporal server address
    """
    registry = get_registry()

    # Discover plugins before running
    registry.discover_plugins()

    # Filter modules if specified
    if modules:
        for name in modules:
            if name not in [m.name for m in registry.get_all_modules()]:
                logger.warning(f"Module {name} not found")

    # Get queues and their modules
    queues = registry.get_queues()

    if not queues:
        logger.error("No modules registered. Nothing to run.")
        return

    # Connect to Temporal
    client = await get_temporal_client(temporal_host)

    # Create workers per queue
    workers = []
    for queue, queue_modules in queues.items():
        # Skip if not in requested modules
        if modules:
            queue_modules = [m for m in queue_modules if m.name in modules]
            if not queue_modules:
                continue

        # Aggregate workflows and activities for this queue
        workflows = []
        activities = []
        for mod in queue_modules:
            workflows.extend(mod.workflows)
            activities.extend(mod.activities)

        if workflows or activities:
            worker = await create_worker(client, queue, workflows, activities)
            workers.append(worker)
            logger.info(f"Created worker for queue: {queue}")
            logger.info(f"  Workflows: {[w.__name__ for w in workflows]}")
            logger.info(f"  Activities: {[a.__name__ for a in activities]}")

    if not workers:
        logger.error("No workers created. Check module configuration.")
        return

    logger.info(f"--- Starting {len(workers)} worker(s) ---")

    # Register in Redis for service discovery
    heartbeat_task = None
    try:
        from contextcore import register_service

        from contextworker.config import get_config

        cfg = get_config()

        instance_name = cfg.worker_instance_name
        temporal_addr = temporal_host or cfg.temporal_host
        tenants_raw = cfg.worker_tenants
        tenants = [t.strip() for t in tenants_raw.split(",") if t.strip()] if tenants_raw else []

        heartbeat_task = await register_service(
            service="worker-temporal",
            instance=instance_name,
            endpoint=temporal_addr,
            tenants=tenants,
            metadata={
                "queues": list(queues.keys()),
                "worker_count": len(workers),
            },
        )
    except Exception as e:
        logger.debug(f"Service discovery registration skipped: {e}")

    # Run all workers concurrently
    try:
        await asyncio.gather(*[w.run() for w in workers])
    finally:
        if heartbeat_task:
            heartbeat_task.cancel()
