"""
Temporal Schedules utilities for contextunity.worker.
Provides helpers for creating and managing scheduled workflows.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass

from contextunity.core import get_contextunit_logger
from contextunity.core.types import is_object_list
from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleSpec,
)

logger = get_contextunit_logger(__name__)


@dataclass
class ScheduleConfig:
    """Configuration for a scheduled Temporal workflow."""

    schedule_id: str
    workflow_name: str
    task_queue: str
    cron: str
    args: list[object] | None = None
    description: str = ""


DEFAULT_SCHEDULES: list[ScheduleConfig] = []


def schedule_config_from_wire(data: dict[str, object]) -> ScheduleConfig:
    """Build ``ScheduleConfig`` from a manifest/RPC schedule dictionary."""
    schedule_id = data.get("schedule_id")
    if not isinstance(schedule_id, str) or not schedule_id:
        raise ValueError("schedule_id is required")

    workflow_name = data.get("workflow_name")
    if not isinstance(workflow_name, str) or not workflow_name:
        raise ValueError("workflow_name is required")

    task_queue = data.get("task_queue")
    if not isinstance(task_queue, str) or not task_queue:
        raise ValueError("task_queue is required")

    cron = data.get("cron")
    if not isinstance(cron, str) or not cron:
        raise ValueError("cron is required")

    args_raw = data.get("args")
    args: list[object] | None = None
    if is_object_list(args_raw):
        args = list(args_raw)

    description_raw = data.get("description")
    description = description_raw if isinstance(description_raw, str) else ""

    return ScheduleConfig(
        schedule_id=schedule_id,
        workflow_name=workflow_name,
        task_queue=task_queue,
        cron=cron,
        args=args,
        description=description,
    )


async def get_temporal_client(host: str | None = None) -> Client:
    """Get Temporal client (host from config if not provided)."""
    if host is None:
        from contextunity.worker.config import get_config

        host = get_config().temporal_host
    return await Client.connect(host)


async def create_schedule(
    client: Client,
    schedule_id: str,
    workflow: str,
    task_queue: str,
    cron: str,
    args: list[object] | None = None,
    workflow_id: str | None = None,
) -> str:
    """Create a Temporal schedule for a workflow."""
    wf_id = workflow_id or f"{schedule_id}-scheduled"

    try:
        _ = await client.create_schedule(
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
        logger.info("Created schedule: %s", schedule_id)
        return schedule_id
    except Exception as exc:
        if "already exists" in str(exc).lower():
            logger.warning("Schedule %s already exists", schedule_id)
            return schedule_id
        raise


async def list_schedules(
    client: Client | None = None,
    temporal_host: str | None = None,
) -> list[dict[str, str | None]]:
    """List all schedules."""
    if client is None:
        client = await get_temporal_client(temporal_host)

    schedules: list[dict[str, str | None]] = []
    async for schedule in await client.list_schedules():
        schedules.append(
            {
                "id": schedule.id,
                "workflow": None,
            }
        )

    return schedules


async def delete_schedule(
    schedule_id: str,
    client: Client | None = None,
    temporal_host: str | None = None,
) -> bool:
    """Delete a schedule by ID."""
    if client is None:
        client = await get_temporal_client(temporal_host)

    try:
        handle = client.get_schedule_handle(schedule_id)
        await handle.delete()
        logger.info("Deleted schedule: %s", schedule_id)
        return True
    except Exception as exc:
        logger.error("Failed to delete schedule %s: %s", schedule_id, exc)
        return False


async def pause_schedule(
    schedule_id: str,
    client: Client | None = None,
    temporal_host: str | None = None,
) -> bool:
    """Pause a schedule."""
    if client is None:
        client = await get_temporal_client(temporal_host)

    try:
        handle = client.get_schedule_handle(schedule_id)
        await handle.pause()
        logger.info("Paused schedule: %s", schedule_id)
        return True
    except Exception as exc:
        logger.error("Failed to pause schedule %s: %s", schedule_id, exc)
        return False


async def unpause_schedule(
    schedule_id: str,
    client: Client | None = None,
    temporal_host: str | None = None,
) -> bool:
    """Unpause a schedule."""
    if client is None:
        client = await get_temporal_client(temporal_host)

    try:
        handle = client.get_schedule_handle(schedule_id)
        await handle.unpause()
        logger.info("Unpaused schedule: %s", schedule_id)
        return True
    except Exception as exc:
        logger.error("Failed to unpause schedule %s: %s", schedule_id, exc)
        return False


def _schedule_command(namespace: argparse.Namespace) -> str:
    """Return the schedule CLI subcommand name."""
    raw = dict(vars(namespace))
    command = raw.get("command")
    if not isinstance(command, str) or not command:
        raise SystemExit("command is required")
    return command


def _schedule_id(namespace: argparse.Namespace) -> str:
    """Return the schedule id positional argument."""
    raw = dict(vars(namespace))
    schedule_id = raw.get("schedule_id")
    if not isinstance(schedule_id, str) or not schedule_id:
        raise SystemExit("schedule_id is required")
    return schedule_id


async def _cli_main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Manage Temporal schedules")
    subparsers = parser.add_subparsers(dest="command", required=True)

    _ = subparsers.add_parser("list", help="List all schedules")

    delete_parser = subparsers.add_parser("delete", help="Delete a schedule")
    _ = delete_parser.add_argument("schedule_id", help="Schedule ID to delete")

    pause_parser = subparsers.add_parser("pause", help="Pause a schedule")
    _ = pause_parser.add_argument("schedule_id", help="Schedule ID to pause")

    unpause_parser = subparsers.add_parser("unpause", help="Unpause a schedule")
    _ = unpause_parser.add_argument("schedule_id", help="Schedule ID to unpause")

    namespace = parser.parse_args()
    command = _schedule_command(namespace)

    logging.basicConfig(level=logging.INFO)

    match command:
        case "list":
            schedules = await list_schedules()
            if schedules:
                for entry in schedules:
                    print(f"  {entry['id']}: {entry['workflow']}")
            else:
                print("No schedules found")
        case "delete":
            _ = await delete_schedule(_schedule_id(namespace))
        case "pause":
            _ = await pause_schedule(_schedule_id(namespace))
        case "unpause":
            _ = await unpause_schedule(_schedule_id(namespace))
        case _:
            raise SystemExit(f"Unknown command: {command!r}")


def main() -> None:
    """Run the CLI schedule command runner."""
    import asyncio

    asyncio.run(_cli_main())


if __name__ == "__main__":
    main()

__all__ = [
    "ScheduleConfig",
    "DEFAULT_SCHEDULES",
    "get_temporal_client",
    "create_schedule",
    "list_schedules",
    "delete_schedule",
    "pause_schedule",
    "unpause_schedule",
    "schedule_config_from_wire",
]
