"""Worker-local type aliases (Temporal engines, schedules, registry)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeAlias

# Temporal @workflow.defn class registered on a worker queue.
WorkflowClass: TypeAlias = type[object]

# Temporal @activity.defn async callable.
ActivityCallable: TypeAlias = Callable[..., Awaitable[object]]

__all__ = [
    "ActivityCallable",
    "WorkflowClass",
]
