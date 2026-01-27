"""Temporal activities for ContextWorker.

Activities are the building blocks of workflows - they represent
individual units of work that can be retried and monitored.
"""

from __future__ import annotations

from typing import Any

from temporalio import activity

from contextcore import get_context_unit_logger

logger = get_context_unit_logger(__name__)


@activity.defn
async def fetch_vendor_data(url: str) -> dict[str, Any]:
    """Activity to fetch raw data (XLS/YML/JSON) from vendor URL.

    Args:
        url: Vendor data source URL

    Returns:
        Dictionary with status, content_type, and raw_ref (S3 path)
    """
    logger.info(f"Fetching data from {url}")
    # Implementation logic for HTTP fetch
    return {
        "status": "success",
        "content_type": "application/xml",
        "raw_ref": "s3://buffer/raw.xml",
    }


@activity.defn
async def parse_raw_payload(payload_info: dict[str, Any]) -> list[dict[str, Any]]:
    """Activity to parse raw vendor payload into a list of items.

    Args:
        payload_info: Dictionary with payload metadata (content_type, raw_ref, etc.)

    Returns:
        List of parsed item dictionaries (sku, name, price, etc.)
    """
    logger.info(f"Parsing payload: {payload_info}")
    # Implementation logic for supplier-specific parsing
    return [{"sku": "SKU-1", "name": "Item 1", "price": 100.0}]


@activity.defn
async def update_staging_buffer(items: list[dict[str, Any]]) -> int:
    """Activity to push parsed items into the harvester.* staging schema.

    Args:
        items: List of parsed item dictionaries

    Returns:
        Number of items successfully inserted/updated
    """
    logger.info(f"Pushing {len(items)} items to staging buffer")
    # Implementation logic for DB upsert
    return len(items)
