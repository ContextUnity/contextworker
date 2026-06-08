"""Episodic memory retention and fact distillation job."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated

import typer
from contextunity.core import get_contextunit_logger
from contextunity.core.sdk import BrainClient
from contextunity.worker.schemas import EpisodeDict, RetentionStats

logger = get_contextunit_logger(__name__)


async def run_retention(
    *,
    tenant_id: str = "default",
    retention_days: int = 30,
    batch_size: int = 100,
    distill: bool = False,
    brain_endpoint: str = "brain.contextunity.ts.net:50051",
    dry_run: bool = False,
) -> RetentionStats:
    """Run episodic memory retention cleanup."""
    from contextunity.worker.core.brain_token import get_brain_service_token

    start = datetime.now()
    brain = BrainClient(
        host=brain_endpoint,
        token=get_brain_service_token(allowed_tenants=(tenant_id,)),
    )

    stats_before = await brain.get_episode_stats(tenant_id=tenant_id)
    total_raw = stats_before.get("total", 0)
    total_before = total_raw if isinstance(total_raw, int) else 0
    logger.info(
        "Retention job started: tenant=%s, retention=%d days, total_episodes=%d",
        tenant_id,
        retention_days,
        total_before,
    )

    if total_before == 0:
        return {
            "tenant_id": tenant_id,
            "retention_days": retention_days,
            "total_before": 0,
            "deleted_count": 0,
            "distilled_facts": 0,
            "duration_ms": 0,
            "dry_run": dry_run,
            "timestamp": datetime.now().isoformat(),
        }

    distilled_count = 0
    processed_ids: list[str] = []

    if distill:
        old_episodes = await brain.get_old_episodes(
            tenant_id=tenant_id,
            older_than_days=retention_days,
            limit=batch_size,
        )

        if old_episodes:
            distilled_count = await _distill_episodes(
                brain=brain,
                episodes=list(old_episodes),
                tenant_id=tenant_id,
                dry_run=dry_run,
            )
            processed_ids = [str(ep.get("id", "")) for ep in old_episodes if ep.get("id")]
            logger.info(
                "Distilled %d facts from %d episodes",
                distilled_count,
                len(old_episodes),
            )

    deleted_count = 0
    if not dry_run:
        if processed_ids:
            deleted_count = await brain.retention_cleanup(
                tenant_id=tenant_id,
                older_than_days=retention_days,
                episode_ids=processed_ids,
            )
        else:
            deleted_count = await brain.retention_cleanup(
                tenant_id=tenant_id,
                older_than_days=retention_days,
            )

    duration_ms = int((datetime.now() - start).total_seconds() * 1000)

    logger.info(
        "Retention job complete: deleted=%d, distilled=%d, duration=%dms",
        deleted_count,
        distilled_count,
        duration_ms,
    )

    return RetentionStats(
        tenant_id=tenant_id,
        retention_days=retention_days,
        total_before=total_before,
        deleted_count=deleted_count,
        distilled_facts=distilled_count,
        duration_ms=duration_ms,
        dry_run=dry_run,
        timestamp=datetime.now().isoformat(),
    )


async def _distill_episodes(
    *,
    brain: BrainClient,
    episodes: list[EpisodeDict],
    tenant_id: str,
    dry_run: bool = False,
) -> int:
    """Distill facts from old episodes."""
    by_user: dict[str, list[EpisodeDict]] = {}
    for ep in episodes:
        uid = ep.get("user_id", "unknown")
        by_user.setdefault(uid, []).append(ep)

    fact_count = 0
    for user_id, user_episodes in by_user.items():
        facts = _extract_facts_simple(user_episodes)

        if dry_run:
            logger.info(
                "DRY RUN: would distill %d facts for user %s from %d episodes",
                len(facts),
                user_id,
                len(user_episodes),
            )
            fact_count += len(facts)
            continue

        for fact_key, fact_value in facts.items():
            try:
                await brain.upsert_fact(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    key=fact_key,
                    value=fact_value,
                    confidence=0.8,
                    source_id=f"retention:{datetime.now().strftime('%Y%m%d')}",
                )
                fact_count += 1
            except Exception as exc:  # graceful-degrade: continue other facts
                logger.warning("Failed to upsert fact %s for %s: %s", fact_key, user_id, exc)

    return fact_count


def _extract_facts_simple(episodes: list[EpisodeDict]) -> dict[str, str]:
    """Simple heuristic fact extraction (no LLM)."""
    facts: dict[str, str] = {}
    facts["total_interactions"] = str(len(episodes))

    dates = [ep.get("created_at", "") for ep in episodes if ep.get("created_at")]
    if dates:
        facts["first_interaction"] = min(dates)
        facts["last_interaction"] = max(dates)

    sessions: set[object] = set()
    for ep in episodes:
        metadata = ep.get("metadata")
        if isinstance(metadata, dict):
            session_id = metadata.get("session_id")
            if session_id is not None:
                sessions.add(session_id)
    if sessions:
        facts["session_count"] = str(len(sessions))

    return facts


def retention_cli(
    tenant: Annotated[str, typer.Option("--tenant", help="Tenant ID")] = "default",
    days: Annotated[int, typer.Option("--days", help="Retention days")] = 30,
    batch: Annotated[int, typer.Option("--batch", help="Batch size")] = 100,
    distill: Annotated[bool, typer.Option("--distill", help="Distill facts before deleting")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Report only, no deletions")] = False,
    brain: Annotated[
        str,
        typer.Option("--brain", help="Brain endpoint"),
    ] = "brain.contextunity.ts.net:50051",
) -> None:
    """CLI entry point for retention job."""
    import asyncio
    import json

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    result = asyncio.run(
        run_retention(
            tenant_id=tenant,
            retention_days=days,
            batch_size=batch,
            distill=distill,
            brain_endpoint=brain,
            dry_run=dry_run,
        )
    )
    print(json.dumps(result, indent=2))


def main() -> None:
    """Run the CLI retention job runner."""
    typer.run(retention_cli)


if __name__ == "__main__":
    main()

__all__ = ["run_retention"]
