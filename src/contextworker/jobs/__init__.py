from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    from .scrum_master import ScrumMasterWorkflow
except ImportError:
    ScrumMasterWorkflow = None  # type: ignore[assignment, misc]
    logger.debug("ScrumMasterWorkflow unavailable (missing worker_sdk)")


def register_all(registry):
    """Register all job workflows and activities into the worker registry."""
    if ScrumMasterWorkflow is None:
        return
    registry.register(
        name="scrum-master",
        queue="scrum-master-tasks",
        workflows=[ScrumMasterWorkflow],
        activities=[],
    )


__all__: list[str] = ["ScrumMasterWorkflow", "register_all"]
