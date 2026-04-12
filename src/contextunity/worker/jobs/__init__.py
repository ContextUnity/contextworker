from __future__ import annotations

from .orchestrator import register_all as register_orchestrator
from .scrum_master import ScrumMasterWorkflow


def register_all(registry):
    """Register all job workflows and activities into the worker registry."""
    registry.register(
        name="scrum-master",
        queue="scrum-master-tasks",
        workflows=[ScrumMasterWorkflow],
        activities=[],
    )
    register_orchestrator(registry)


__all__: list[str] = ["ScrumMasterWorkflow", "register_all"]
