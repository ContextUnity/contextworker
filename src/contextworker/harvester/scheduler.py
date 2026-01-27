"""
Scheduler for Harvester enrichment jobs.

Uses APScheduler to periodically:
1. Query pending products from DB
2. Enqueue them to Router's shared Redis queue
3. Monitor queue status

Note: Actual processing done by Gardener graph (triggered separately or via HTTP).
"""

import logging
from typing import List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .config import HarvesterConfig

logger = logging.getLogger(__name__)


class HarvesterScheduler:
    """Scheduler for harvester background jobs.

    Enqueues products to Router's shared Redis queue.
    """

    def __init__(self, config: HarvesterConfig):
        self.config = config
        self.scheduler = AsyncIOScheduler()
        self._queue = None

    async def _get_queue(self):
        """Get Router's enrichment queue."""
        if self._queue is None:
            from contextrouter.cortex.queue import get_enrichment_queue

            self._queue = get_enrichment_queue(self.config.redis_url)
        return self._queue

    def start(self):
        """Start the scheduler."""
        gardener_cfg = self.config.gardener

        # Enqueue job - find pending products and add to queue
        self.scheduler.add_job(
            self._enqueue_pending_products,
            trigger=IntervalTrigger(seconds=gardener_cfg.poll_interval),
            id="harvester_enqueue",
            name="Harvester Enqueue Pending Products",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info(
            f"Harvester scheduler started. Polling every {gardener_cfg.poll_interval}s"
        )

    async def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        if self._queue:
            await self._queue.close()
            self._queue = None
        logger.info("Harvester scheduler stopped")

    async def _enqueue_pending_products(self):
        """Find pending products and enqueue to Router."""
        cfg = self.config

        # Validate required config
        if not cfg.tenant_id:
            logger.error("TENANT_ID not configured")
            return

        if not cfg.database_url:
            logger.error("DATABASE_URL not configured")
            return

        try:
            # Get pending products from DB
            product_ids = await self._get_pending_products()

            if not product_ids:
                logger.debug("No pending products to enqueue")
                return

            # Enqueue to Router's shared queue
            queue = await self._get_queue()
            enqueued = await queue.enqueue(
                product_ids=product_ids,
                tenant_id=cfg.tenant_id,
                priority="normal",
                source="scheduler",
            )

            logger.info(
                f"Enqueued {enqueued}/{len(product_ids)} products to enrichment queue"
            )

            # Log queue stats
            stats = await queue.get_queue_stats(cfg.tenant_id)
            logger.info(f"Queue stats: {stats}")

        except Exception as e:
            logger.exception(f"Enqueue failed: {e}")

    async def _get_pending_products(self) -> List[int]:
        """Query DB for products needing enrichment."""
        import psycopg
        from psycopg.rows import dict_row

        batch_size = self.config.gardener.batch_size

        async with await psycopg.AsyncConnection.connect(
            self.config.database_url, row_factory=dict_row
        ) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT id
                    FROM harvester_dealer_product
                    WHERE 
                        status IN ('raw', 'enriching')
                        AND (
                            enrichment->>'taxonomy' IS NULL
                            OR enrichment->'taxonomy'->>'status' IN ('pending', 'error')
                            OR enrichment->>'ner' IS NULL
                            OR enrichment->'ner'->>'status' IN ('pending', 'error')
                        )
                    ORDER BY created_at
                    LIMIT %s
                """,
                    (batch_size,),
                )

                rows = await cur.fetchall()
                return [row["id"] for row in rows]


# CLI entry point
async def run_scheduler():
    """Run scheduler (for testing or standalone)."""
    config = HarvesterConfig.from_env()
    scheduler = HarvesterScheduler(config)

    try:
        scheduler.start()
        # Keep running
        import asyncio

        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        await scheduler.stop()


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_scheduler())
