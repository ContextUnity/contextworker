"""Temporal workflows for ContextWorker.

Workflows orchestrate activities and provide durability, retries,
and state management for long-running business processes.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow

from .activities import fetch_vendor_data, parse_raw_payload, update_staging_buffer


@workflow.defn
class HarvesterImportWorkflow:
    """Workflow for importing vendor data into the harvester staging schema.

    This workflow orchestrates the three-step process:
    1. Fetch raw data from vendor URL
    2. Parse raw payload into structured items
    3. Stage parsed items in the database
    """

    @workflow.run
    async def run(self, vendor_url: str) -> str:
        """Execute the harvester import workflow.

        Args:
            vendor_url: URL to fetch vendor data from

        Returns:
            Success message with count of imported items
        """
        # 1. Fetch
        raw_data = await workflow.execute_activity(
            fetch_vendor_data,
            vendor_url,
            start_to_close_timeout=timedelta(minutes=5),
        )

        # 2. Parse
        items = await workflow.execute_activity(
            parse_raw_payload,
            raw_data,
            start_to_close_timeout=timedelta(minutes=10),
        )

        # 3. Stage
        count = await workflow.execute_activity(
            update_staging_buffer,
            items,
            start_to_close_timeout=timedelta(minutes=5),
        )

        return f"Successfully imported {count} items from {vendor_url}"
