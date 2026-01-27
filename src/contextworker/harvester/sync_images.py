"""
Image sync module for Worker.

Syncs product images to CDN (Cloudflare R2).
Uses Brain gRPC to get products with pending images.

Usage:
    python -m contextworker.harvester.sync_images --project traverse
"""

import argparse
import asyncio
import hashlib
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class ImageSyncWorker:
    """Background worker to sync product images to Cloudflare R2."""

    def __init__(
        self,
        brain_url: str = "localhost:50051",
        tenant_id: str = "traverse",
        batch_size: int = 100,
        rate_limit: float = 10.0,
        concurrency: int = 5,
        retry_attempts: int = 3,
    ):
        self.brain_url = brain_url
        self.tenant_id = tenant_id
        self.batch_size = batch_size
        self.rate_limit = rate_limit
        self.concurrency = concurrency
        self.retry_attempts = retry_attempts
        self._brain_client = None

        # CDN config from env
        self.cdn_endpoint = os.getenv("R2_ENDPOINT")
        self.cdn_bucket = os.getenv("R2_BUCKET", "product-images")
        self.cdn_access_key = os.getenv("R2_ACCESS_KEY")
        self.cdn_secret_key = os.getenv("R2_SECRET_KEY")

        self.stats = {
            "processed": 0,
            "uploaded": 0,
            "failed": 0,
            "skipped": 0,
        }

    async def _get_brain_client(self):
        """Lazy Brain gRPC client."""
        if self._brain_client is None:
            from contextcore import BrainClient

            self._brain_client = BrainClient(self.brain_url)
        return self._brain_client

    async def sync_all(
        self,
        dealer_code: str = None,
        retry_errors: bool = False,
    ) -> dict[str, int]:
        """Sync all images that need uploading.

        Gets products with pending images from Brain gRPC.
        """
        logger.info(f"Starting image sync (concurrency={self.concurrency})")

        brain = await self._get_brain_client()

        # Get products with pending images
        products = await brain.get_products_pending_images(
            tenant_id=self.tenant_id,
            dealer_code=dealer_code,
            retry_errors=retry_errors,
            limit=10000,
        )

        logger.info(f"Found {len(products)} products with images to sync")

        # Process in batches
        for i in range(0, len(products), self.batch_size):
            batch = products[i : i + self.batch_size]
            batch_num = i // self.batch_size + 1
            logger.info(f"Processing batch {batch_num} ({len(batch)} items)")

            await self._process_batch_parallel(batch)

        logger.info(f"Image sync completed: {self.stats}")
        return self.stats

    async def _process_batch_parallel(self, products: list[dict[str, Any]]):
        """Process a batch of products in parallel."""
        loop = asyncio.get_event_loop()

        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            futures = {
                executor.submit(self._sync_product_safe, p): p["id"] for p in products
            }

            for future in as_completed(futures):
                try:
                    await loop.run_in_executor(None, future.result)
                except Exception as e:
                    pid = futures[future]
                    logger.error(f"Error processing product {pid}: {e}")

    def _sync_product_safe(self, product: dict[str, Any]) -> None:
        """Sync single product images (thread-safe)."""
        try:
            self._sync_product(product)
        except Exception as e:
            self.stats["failed"] += 1
            logger.exception(f"Failed to sync product {product['id']}: {e}")

    def _sync_product(self, product: dict[str, Any]) -> None:
        """Sync single product images."""
        self.stats["processed"] += 1

        image_urls = product.get("image_urls", [])
        if not image_urls:
            self.stats["skipped"] += 1
            return

        for url in image_urls:
            try:
                # Download image
                response = httpx.get(url, timeout=30.0)
                response.raise_for_status()

                # Generate CDN path
                url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                ext = Path(url).suffix or ".jpg"
                cdn_path = f"{self.tenant_id}/{product['dealer_code']}/{product['sku']}_{url_hash}{ext}"

                # Upload to CDN
                self._upload_to_cdn(cdn_path, response.content)

                self.stats["uploaded"] += 1

            except Exception as e:
                logger.warning(f"Failed to sync image {url}: {e}")

    def _upload_to_cdn(self, path: str, content: bytes) -> str:
        """Upload image to Cloudflare R2."""
        if not self.cdn_endpoint:
            logger.warning("R2_ENDPOINT not configured, skipping upload")
            return ""

        # TODO: Implement actual R2 upload using boto3 or similar
        # For now, just log
        logger.debug(f"Would upload {len(content)} bytes to {path}")
        return f"https://{self.cdn_bucket}.{self.cdn_endpoint}/{path}"

    async def close(self):
        """Close Brain connection."""
        if self._brain_client:
            await self._brain_client.close()
            self._brain_client = None


async def run_sync(
    project: str,
    dealer_code: str = None,
    retry_errors: bool = False,
) -> dict:
    """Run image sync for a project."""
    brain_url = os.getenv("BRAIN_GRPC_URL", "localhost:50051")
    tenant_id = os.getenv("TENANT_ID", project)

    worker = ImageSyncWorker(
        brain_url=brain_url,
        tenant_id=tenant_id,
    )

    try:
        return await worker.sync_all(
            dealer_code=dealer_code,
            retry_errors=retry_errors,
        )
    finally:
        await worker.close()


def main():
    parser = argparse.ArgumentParser(description="Sync product images to CDN")
    parser.add_argument(
        "--project",
        "-p",
        default=os.getenv("DEFAULT_PROJECT"),
        help="Project name",
    )
    parser.add_argument(
        "--dealer",
        help="Specific dealer to sync",
    )
    parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="Retry previously failed images",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose logging",
    )

    args = parser.parse_args()

    if not args.project:
        parser.error("Project not specified. Use --project or set DEFAULT_PROJECT")

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    result = asyncio.run(
        run_sync(
            project=args.project,
            dealer_code=args.dealer,
            retry_errors=args.retry_errors,
        )
    )

    print(f"Sync complete: {result}")


if __name__ == "__main__":
    main()
