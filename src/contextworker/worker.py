"""ContextWorker - High-performance Temporal Worker for ContextUnity.

This module provides Temporal workflows and activities for long-running,
distributed tasks in the ContextUnity ecosystem.
"""

from __future__ import annotations

import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

from contextcore import (
    setup_logging,
    get_context_unit_logger,
    load_shared_config_from_env,
)

from .activities import fetch_vendor_data, parse_raw_payload, update_staging_buffer
from .activities_advanced import process_product_images, generate_seo_content
from .workflows import HarvesterImportWorkflow

logger = get_context_unit_logger(__name__)


async def main() -> None:
    """Main entry point for ContextWorker.

    Connects to Temporal server and starts processing workflows and activities.
    Optionally starts a gRPC server for remote orchestration.
    """
    # Setup logging from SharedConfig
    config = load_shared_config_from_env()
    setup_logging(config=config, service_name="contextworker")

    # Connect to temporal server (managed by traverse-cli)
    temporal_host = os.getenv("TEMPORAL_HOST", "localhost:7233")
    grpc_port = int(os.getenv("WORKER_GRPC_PORT", "50052"))

    client = await Client.connect(temporal_host)

    # Run the worker for orchestration
    worker = Worker(
        client,
        task_queue="harvester-tasks",
        workflows=[HarvesterImportWorkflow],
        activities=[
            fetch_vendor_data,
            parse_raw_payload,
            update_staging_buffer,
            process_product_images,
            generate_seo_content,
        ],
    )

    # Start both Temporal worker and gRPC service
    from .service import serve

    logger.info("--- ContextWorker starting (Temporal + gRPC on %s) ---", grpc_port)

    await asyncio.gather(
        worker.run(), serve(port=grpc_port, temporal_host=temporal_host)
    )


if __name__ == "__main__":
    asyncio.run(main())
