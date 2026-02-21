"""Episodic memory retention and fact distillation job.

Background job that runs daily to:
1. Find episodes older than the retention window (default: 30 days)
2. Optionally distill facts from old episodes via LLM
3. Delete processed episodes from Brain

Schedule: daily at 03:00 UTC (via Temporal or standalone)

Usage:
    # As Temporal activity (from Worker)
    from contextworker.jobs.retention import run_retention

    deleted = await run_retention(tenant_id="default", retention_days=30)

    # Standalone (CLI)
    python -m contextworker.jobs.retention --tenant default --days 30
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


async def run_retention(
    *,
    tenant_id: str = "default",
    retention_days: int = 30,
    batch_size: int = 100,
    distill: bool = False,
    brain_endpoint: str = "brain.contextunity.ts.net:50051",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run episodic memory retention cleanup.

    Args:
        tenant_id: Tenant to clean up.
        retention_days: Delete episodes older than this many days.
        batch_size: Max episodes to process per batch.
        distill: If True, distill facts from old episodes before deleting.
        brain_endpoint: Brain gRPC endpoint.
        dry_run: If True, only report what would be deleted.

    Returns:
        Dict with stats: deleted_count, distilled_facts, duration_ms.
    """
    from contextcore import BrainClient

    from contextworker.core.brain_token import get_brain_service_token

    start = datetime.now()
    brain = BrainClient(host=brain_endpoint, mode="grpc", token=get_brain_service_token())

    # 1. Get stats before
    stats_before = await brain.get_episode_stats(tenant_id=tenant_id)
    total_before = stats_before.get("total", 0)
    logger.info(
        "Retention job started: tenant=%s, retention=%d days, total_episodes=%d",
        tenant_id,
        retention_days,
        total_before,
    )

    if total_before == 0:
        return {
            "tenant_id": tenant_id,
            "total_before": 0,
            "deleted_count": 0,
            "distilled_facts": 0,
            "duration_ms": 0,
            "dry_run": dry_run,
        }

    # 2. Optionally distill facts from old episodes
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
                episodes=old_episodes,
                tenant_id=tenant_id,
                dry_run=dry_run,
            )
            processed_ids = [ep["id"] for ep in old_episodes if ep.get("id")]
            logger.info(
                "Distilled %d facts from %d episodes",
                distilled_count,
                len(old_episodes),
            )

    # 3. Delete old episodes
    deleted_count = 0
    if not dry_run:
        if processed_ids:
            # Delete only the episodes we've distilled
            deleted_count = await brain.retention_cleanup(
                tenant_id=tenant_id,
                older_than_days=retention_days,
                episode_ids=processed_ids,
            )
        else:
            # Bulk delete by age
            deleted_count = await brain.retention_cleanup(
                tenant_id=tenant_id,
                older_than_days=retention_days,
            )

    duration_ms = int((datetime.now() - start).total_seconds() * 1000)

    result = {
        "tenant_id": tenant_id,
        "retention_days": retention_days,
        "total_before": total_before,
        "deleted_count": deleted_count,
        "distilled_facts": distilled_count,
        "duration_ms": duration_ms,
        "dry_run": dry_run,
        "timestamp": datetime.now().isoformat(),
    }

    logger.info(
        "Retention job complete: deleted=%d, distilled=%d, duration=%dms",
        deleted_count,
        distilled_count,
        duration_ms,
    )
    return result


async def _distill_episodes(
    *,
    brain: Any,
    episodes: list[dict],
    tenant_id: str,
    dry_run: bool = False,
) -> int:
    """Distill facts from old episodes.

    Groups episodes by user_id, then for each user:
    - Concatenate episode contents
    - Extract persistent facts (heuristic for now, LLM later)
    - Upsert facts into Entity Memory

    Returns count of facts distilled.
    """
    # Group by user
    by_user: dict[str, list[dict]] = {}
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
                    confidence=0.8,  # Distilled facts have lower confidence
                    source_id=f"retention:{datetime.now().strftime('%Y%m%d')}",
                )
                fact_count += 1
            except Exception as e:
                logger.warning("Failed to upsert fact %s for %s: %s", fact_key, user_id, e)

    return fact_count


def _extract_facts_simple(episodes: list[dict]) -> dict[str, str]:
    """Simple heuristic fact extraction (no LLM).

    Extracts basic statistics as facts. LLM-based extraction
    will be added in a future iteration.
    """
    facts: dict[str, str] = {}

    # Count interactions
    facts["total_interactions"] = str(len(episodes))

    # Date range
    dates = [ep.get("created_at", "") for ep in episodes if ep.get("created_at")]
    if dates:
        facts["first_interaction"] = min(dates)
        facts["last_interaction"] = max(dates)

    # Session count
    sessions = {ep.get("metadata", {}).get("session_id") for ep in episodes}
    sessions.discard(None)
    if sessions:
        facts["session_count"] = str(len(sessions))

    return facts


# ── CLI entry point ──


async def _cli_main():
    """CLI entry point for retention job."""
    import argparse

    parser = argparse.ArgumentParser(description="Episodic memory retention cleanup")
    parser.add_argument("--tenant", default="default", help="Tenant ID")
    parser.add_argument("--days", type=int, default=30, help="Retention days")
    parser.add_argument("--batch", type=int, default=100, help="Batch size")
    parser.add_argument("--distill", action="store_true", help="Distill facts before deleting")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no deletions")
    parser.add_argument(
        "--brain",
        default="brain.contextunity.ts.net:50051",
        help="Brain endpoint",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    result = await run_retention(
        tenant_id=args.tenant,
        retention_days=args.days,
        batch_size=args.batch,
        distill=args.distill,
        brain_endpoint=args.brain,
        dry_run=args.dry_run,
    )

    import json

    print(json.dumps(result, indent=2))


def main():
    import asyncio

    asyncio.run(_cli_main())


if __name__ == "__main__":
    main()


__all__ = ["run_retention"]
