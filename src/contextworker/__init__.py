"""
ContextWorker - Temporal Worker Infrastructure for ContextUnity.

Provides utilities for running Temporal workers:
- WorkerRegistry: Module registration and discovery
- create_worker, run_workers: Temporal worker factory

Usage:
    from contextworker import get_registry, run_workers
    
    registry = get_registry()
    registry.register(
        name="harvest",
        queue="commerce-tasks",
        workflows=[HarvestWorkflow],
        activities=[fetch_products, save_products],
    )
    
    await run_workers()
"""

__version__ = "0.1.0"

from .core import (
    WorkerRegistry,
    get_registry,
    create_worker,
    run_workers,
)
from .core.worker import get_temporal_client
from .config import WorkerConfig, get_config
from .schedules import create_schedule, list_schedules, delete_schedule

__all__ = [
    "__version__",
    # Core
    "WorkerRegistry",
    "get_registry",
    "create_worker",
    "run_workers",
    "get_temporal_client",
    # Config
    "WorkerConfig",
    "get_config",
    # Schedules
    "create_schedule",
    "list_schedules",
    "delete_schedule",
]
