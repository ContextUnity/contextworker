"""
Temporal Schedules utilities for ContextWorker.

Provides helpers for creating and managing scheduled workflows.

Usage:
    # CLI
    python -m contextworker.schedules list
    python -m contextworker.schedules delete my-schedule-id

    # Python
    from contextworker.schedules import create_schedule, list_schedules

    await create_schedule(
        client=client,
        schedule_id="harvest-daily",
        workflow=HarvestWorkflow.run,
        args=["vysota"],
        task_queue="commerce-tasks",
        cron="0 6 * * *",
    )
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, List, Optional

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleSpec,
)

logger = logging.getLogger(__name__)


async def get_temporal_client(host: str = None) -> Client:
    """Get Temporal client."""
    if host is None:
        host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    return await Client.connect(host)


async def create_schedule(
    client: Client,
    schedule_id: str,
    workflow: Callable,
    task_queue: str,
    cron: str,
    args: Optional[List[Any]] = None,
    workflow_id: Optional[str] = None,
) -> str:
    """Create a Temporal schedule for a workflow.

    Args:
        client: Temporal client
        schedule_id: Unique schedule identifier
        workflow: Workflow run method (e.g., MyWorkflow.run)
        task_queue: Task queue name
        cron: Cron expression (e.g., "0 6 * * *" for 6 AM daily)
        args: Arguments to pass to workflow
        workflow_id: Optional workflow ID (defaults to schedule_id)

    Returns:
        Schedule ID
    """
    wf_id = workflow_id or f"{schedule_id}-scheduled"

    try:
        await client.create_schedule(
            schedule_id,
            Schedule(
                action=ScheduleActionStartWorkflow(
                    workflow,
                    args=args or [],
                    id=wf_id,
                    task_queue=task_queue,
                ),
                spec=ScheduleSpec(
                    cron_expressions=[cron],
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


async def list_schedules(
    client: Client = None,
    temporal_host: str = None,
) -> List[dict]:
    """List all schedules."""
    if client is None:
        client = await get_temporal_client(temporal_host)

    schedules = []
    async for schedule in client.list_schedules():
        schedules.append(
            {
                "id": schedule.id,
                "workflow": schedule.info.action.workflow
                if schedule.info.action
                else None,
            }
        )

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


async def pause_schedule(
    schedule_id: str,
    client: Client = None,
    temporal_host: str = None,
) -> bool:
    """Pause a schedule."""
    if client is None:
        client = await get_temporal_client(temporal_host)

    try:
        handle = client.get_schedule_handle(schedule_id)
        await handle.pause()
        logger.info(f"Paused schedule: {schedule_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to pause schedule {schedule_id}: {e}")
        return False


async def unpause_schedule(
    schedule_id: str,
    client: Client = None,
    temporal_host: str = None,
) -> bool:
    """Unpause a schedule."""
    if client is None:
        client = await get_temporal_client(temporal_host)

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

    parser = argparse.ArgumentParser(description="Manage Temporal schedules")
    subparsers = parser.add_subparsers(dest="command", required=True)

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

    if args.command == "list":
        schedules = await list_schedules()
        if schedules:
            for s in schedules:
                print(f"  {s['id']}: {s['workflow']}")
        else:
            print("No schedules found")

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


__all__ = [
    "get_temporal_client",
    "create_schedule",
    "list_schedules",
    "delete_schedule",
    "pause_schedule",
    "unpause_schedule",
]
