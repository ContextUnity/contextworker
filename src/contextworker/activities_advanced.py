"""Advanced Temporal activities for ContextWorker.

These activities perform more complex operations like image processing
and LLM-based content generation.
"""

from __future__ import annotations

from typing import Any

from temporalio import activity

from contextcore import get_context_unit_logger

logger = get_context_unit_logger(__name__)


@activity.defn
async def process_product_images(image_urls: list[str]) -> list[str]:
    """Downloads, resizes, and optimizes images for the catalog.

    Args:
        image_urls: List of image URLs to process

    Returns:
        List of processed image paths (local or S3)
    """
    logger.info(f"Processing {len(image_urls)} images")
    processed_paths: list[str] = []
    # Placeholder: Actual image processing logic (PIL/Sharp)
    for url in image_urls:
        processed_paths.append(f"processed/{url.split('/')[-1]}")

    return processed_paths


@activity.defn
async def generate_seo_content(product_data: dict[str, Any]) -> dict[str, str]:
    """Generates SEO meta tags and descriptions using LLM.

    Args:
        product_data: Dictionary with product information (name, description, etc.)

    Returns:
        Dictionary with meta_title and meta_description
    """
    product_name = product_data.get("name", "Product")
    logger.info(f"Generating SEO for {product_name}")
    # Placeholder: Call Lexicon agent via Router
    return {
        "meta_title": f"Buy {product_name} Online",
        "meta_description": f"Best price for {product_name} at Traverse.",
    }
