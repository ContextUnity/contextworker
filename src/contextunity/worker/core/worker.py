"""
Temporal Worker Factory.

Creates and runs Temporal workers based on registered modules.
"""

from __future__ import annotations

import asyncio

from contextunity.core import get_contextunit_logger
from contextunity.worker.types import ActivityCallable, WorkflowClass
from temporalio.client import Client
from temporalio.worker import Worker

from .registry import get_registry

logger = get_contextunit_logger(__name__)


async def get_temporal_client(host: str | None = None) -> Client:
    """Get Temporal client connection (host from config if not provided)."""
    if host is None:
        from ..config import get_config

        host = get_config().temporal_host
    return await Client.connect(host)


async def create_worker(
    client: Client,
    queue: str,
    workflows: list[WorkflowClass] | None = None,
    activities: list[ActivityCallable] | None = None,
) -> Worker:
    """Create a Temporal worker for a specific queue."""
    return Worker(
        client,
        task_queue=queue,
        workflows=workflows or [],
        activities=activities or [],
    )


async def run_workers(
    modules: list[str] | None = None,
    temporal_host: str | None = None,
) -> None:
    """Run Temporal workers for specified modules."""
    registry = get_registry()
    registry.discover_plugins()

    if modules:
        known = {m.name for m in registry.get_all_modules()}
        for name in modules:
            if name not in known:
                logger.warning("Module %s not found", name)

    queues = registry.get_queues()

    if not queues:
        logger.error("No modules registered. Nothing to run.")
        return

    client = await get_temporal_client(temporal_host)

    workers: list[Worker] = []
    for queue, queue_modules in queues.items():
        if modules:
            queue_modules = [m for m in queue_modules if m.name in modules]
            if not queue_modules:
                continue

        workflows: list[WorkflowClass] = []
        activities: list[ActivityCallable] = []
        for mod in queue_modules:
            workflows.extend(mod.workflows)
            activities.extend(mod.activities)

        if workflows or activities:
            worker = await create_worker(client, queue, workflows, activities)
            workers.append(worker)
            logger.info("Created worker for queue: %s", queue)
            logger.info("  Workflows: %s", [w.__name__ for w in workflows])
            logger.info("  Activities: %s", [a.__name__ for a in activities])

    if not workers:
        logger.error("No workers created. Check module configuration.")
        return

    logger.info("--- Starting %d worker(s) ---", len(workers))

    heartbeat_task = None
    try:
        from contextunity.core import register_service
        from contextunity.worker.config import get_config

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
    except Exception as exc:  # graceful-degrade: discovery is optional
        logger.debug("Service discovery registration skipped: %s", exc)

    try:
        _ = await asyncio.gather(*[w.run() for w in workers])
    finally:
        if heartbeat_task:
            _ = heartbeat_task.cancel()


__all__ = ["create_worker", "get_temporal_client", "run_workers"]
