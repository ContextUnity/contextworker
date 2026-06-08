"""Worker background job definitions and orchestrators."""

from __future__ import annotations

from contextunity.worker.core.registry import WorkerRegistry

from .orchestrator import register_all as register_orchestrator


def register_all(registry: WorkerRegistry) -> None:
    """Register all job workflows and activities into the worker registry."""
    register_orchestrator(registry)


__all__: list[str] = ["register_all"]
