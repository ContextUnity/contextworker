"""Centralized schemas for contextunity.worker."""

from __future__ import annotations

from typing import TypedDict

from contextunity.core.types import JsonDict


class RetentionStats(TypedDict):
    """Result of an episodic memory retention cleanup job."""

    tenant_id: str
    retention_days: int
    total_before: int
    deleted_count: int
    distilled_facts: int
    duration_ms: int
    dry_run: bool
    timestamp: str


class EpisodeDict(TypedDict, total=False):
    """A single episode from Brain memory."""

    id: str
    user_id: str
    created_at: str
    metadata: JsonDict
