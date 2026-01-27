"""
Temporal Schedules for Worker modules.

Provides utilities for creating and managing scheduled workflows.
Replaces APScheduler with Temporal's native scheduling.

Usage:
    # CLI
    python -m contextworker.schedules create
    python -m contextworker.schedules list
    python -m contextworker.schedules delete gardener-every-5min
    
    # Python
    from contextworker.schedules import create_default_schedules
    await create_default_schedules(client, tenant_id="traverse")
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import timedelta
from typing import List, Optional

from temporalio.client import Client, Schedule, ScheduleActionStartWorkflow, ScheduleSpec

logger = logging.getLogger(__name__)


@dataclass
class ScheduleConfig:
    """Configuration for a scheduled workflow."""
    
    schedule_id: str
    workflow_name: str
    workflow_class: type
    task_queue: str
    cron: str
    args: list = None
    description: str = ""


# Default schedules for Worker modules
DEFAULT_SCHEDULES = [
    ScheduleConfig(
        schedule_id="harvester-daily",
        workflow_name="HarvestWorkflow",
        workflow_class=None,  # Set at runtime
        task_queue="harvest-tasks",
        cron="0 6 * * *",  # Every day at 6 AM
        args=["all"],  # supplier_code="all" means run all suppliers
        description="Daily harvest of all suppliers",
    ),
    ScheduleConfig(
        schedule_id="gardener-every-5min",
        workflow_name="GardenerWorkflow",
        workflow_class=None,
        task_queue="gardener-tasks",
        cron="*/5 * * * *",  # Every 5 minutes
        args=[],  # tenant_id added at runtime
        description="Enrich pending products every 5 minutes",
    ),
]


async def get_temporal_client(host: str = None) -> Client:
    """Get Temporal client."""
    if host is None:
        host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    return await Client.connect(host)


async def create_schedule(
    client: Client,
    config: ScheduleConfig,
    tenant_id: str,
) -> str:
    """Create a Temporal schedule for a workflow.
    
    Returns:
        Schedule ID
    """
    from .modules.harvester import HarvestWorkflow
    from .modules.gardener import GardenerWorkflow
    
    # Map workflow names to classes
    workflow_map = {
        "HarvestWorkflow": HarvestWorkflow,
        "GardenerWorkflow": GardenerWorkflow,
    }
    
    workflow_class = workflow_map.get(config.workflow_name)
    if not workflow_class:
        raise ValueError(f"Unknown workflow: {config.workflow_name}")
    
    # Build args with tenant_id
    args = list(config.args) if config.args else []
    if config.workflow_name == "GardenerWorkflow":
        args = [tenant_id, 50, 10]  # tenant_id, batch_size, max_batches
    elif config.workflow_name == "HarvestWorkflow":
        # For harvest, first arg is supplier_code, second is tenant_id
        if args and args[0] == "all":
            args = ["all", tenant_id]
        else:
            args.append(tenant_id)
    
    schedule_id = f"{config.schedule_id}-{tenant_id}"
    
    try:
        await client.create_schedule(
            schedule_id,
            Schedule(
                action=ScheduleActionStartWorkflow(
                    workflow_class.run,
                    args=args,
                    id=f"{config.workflow_name.lower()}-scheduled-{tenant_id}",
                    task_queue=config.task_queue,
                ),
                spec=ScheduleSpec(
                    cron_expressions=[config.cron],
                ),
            ),
        )
        logger.info(f"Created schedule: {schedule_id}")
        return schedule_id
    except Exception as e:
        if "already exists" in str(e).lower():
            logger.warning(f"Schedule {schedule_id} already exists")
            return schedule_id
        raise


async def create_default_schedules(
    client: Client = None,
    tenant_id: str = None,
    temporal_host: str = None,
) -> List[str]:
    """Create all default schedules for a tenant.
    
    Returns:
        List of created schedule IDs
    """
    if client is None:
        client = await get_temporal_client(temporal_host)
    
    if tenant_id is None:
        tenant_id = os.getenv("TENANT_ID", "default")
    
    schedule_ids = []
    for config in DEFAULT_SCHEDULES:
        try:
            sid = await create_schedule(client, config, tenant_id)
            schedule_ids.append(sid)
        except Exception as e:
            logger.error(f"Failed to create schedule {config.schedule_id}: {e}")
    
    return schedule_ids


async def list_schedules(client: Client = None, temporal_host: str = None) -> List[dict]:
    """List all schedules."""
    if client is None:
        client = await get_temporal_client(temporal_host)
    
    schedules = []
    async for schedule in client.list_schedules():
        schedules.append({
            "id": schedule.id,
            "workflow": schedule.info.action.workflow if schedule.info.action else None,
        })
    
    return schedules


async def delete_schedule(
    schedule_id: str,
    client: Client = None,
    temporal_host: str = None,
) -> bool:
    """Delete a schedule by ID."""
    if client is None:
        client = await get_temporal_client(temporal_host)
    
    try:
        handle = client.get_schedule_handle(schedule_id)
        await handle.delete()
        logger.info(f"Deleted schedule: {schedule_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete schedule {schedule_id}: {e}")
        return False


async def pause_schedule(schedule_id: str, client: Client = None) -> bool:
    """Pause a schedule."""
    if client is None:
        client = await get_temporal_client()
    
    try:
        handle = client.get_schedule_handle(schedule_id)
        await handle.pause()
        logger.info(f"Paused schedule: {schedule_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to pause schedule {schedule_id}: {e}")
        return False


async def unpause_schedule(schedule_id: str, client: Client = None) -> bool:
    """Unpause a schedule."""
    if client is None:
        client = await get_temporal_client()
    
    try:
        handle = client.get_schedule_handle(schedule_id)
        await handle.unpause()
        logger.info(f"Unpaused schedule: {schedule_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to unpause schedule {schedule_id}: {e}")
        return False


# CLI
async def _cli_main():
    """CLI entry point."""
    import argparse
    import asyncio
    
    parser = argparse.ArgumentParser(description="Manage Temporal schedules")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # create
    create_parser = subparsers.add_parser("create", help="Create default schedules")
    create_parser.add_argument("--tenant-id", default=None, help="Tenant ID")
    
    # list
    subparsers.add_parser("list", help="List all schedules")
    
    # delete
    delete_parser = subparsers.add_parser("delete", help="Delete a schedule")
    delete_parser.add_argument("schedule_id", help="Schedule ID to delete")
    
    # pause
    pause_parser = subparsers.add_parser("pause", help="Pause a schedule")
    pause_parser.add_argument("schedule_id", help="Schedule ID to pause")
    
    # unpause
    unpause_parser = subparsers.add_parser("unpause", help="Unpause a schedule")
    unpause_parser.add_argument("schedule_id", help="Schedule ID to unpause")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    if args.command == "create":
        ids = await create_default_schedules(tenant_id=args.tenant_id)
        print(f"Created {len(ids)} schedules: {ids}")
    
    elif args.command == "list":
        schedules = await list_schedules()
        for s in schedules:
            print(f"  {s['id']}: {s['workflow']}")
    
    elif args.command == "delete":
        await delete_schedule(args.schedule_id)
    
    elif args.command == "pause":
        await pause_schedule(args.schedule_id)
    
    elif args.command == "unpause":
        await unpause_schedule(args.schedule_id)


def main():
    import asyncio
    asyncio.run(_cli_main())


if __name__ == "__main__":
    main()
