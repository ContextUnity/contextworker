"""ContextWorker — unified entry point.

Start the gRPC service (default):
    python -m contextworker

Start Temporal worker (all modules):
    python -m contextworker --temporal

Start Temporal worker (specific modules):
    python -m contextworker --temporal --modules harvest gardener
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys


def setup_logging(level: str = "INFO"):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="ContextWorker — The Hands of ContextUnity")
    parser.add_argument(
        "--temporal",
        action="store_true",
        help="Start Temporal worker instead of gRPC service",
    )
    parser.add_argument(
        "--modules",
        "-m",
        nargs="*",
        help="Temporal modules to run (default: all discovered). Only with --temporal",
    )
    parser.add_argument(
        "--temporal-host",
        default=None,
        help="Temporal server address (default: TEMPORAL_HOST env or localhost:7233)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level",
    )

    args = parser.parse_args()
    logger = logging.getLogger(__name__)

    if args.temporal:
        # --- Temporal worker mode ---
        setup_logging(args.log_level)

        from .core.registry import get_registry

        registry = get_registry()
        registry.discover_plugins()

        modules = registry.get_all_modules()
        if modules:
            logger.info("Registered modules:")
            for module in modules:
                status = "✓" if module.enabled else "✗"
                logger.info(f"  [{status}] {module.name} -> {module.queue}")
        else:
            logger.warning("No modules discovered. Register modules before running.")
            logger.info("Example:")
            logger.info("  from contextworker import get_registry")
            logger.info("  registry = get_registry()")
            logger.info("  registry.register('mymodule', 'my-queue', [Workflow], [activity])")
            sys.exit(1)

        from .core.worker import run_workers

        try:
            asyncio.run(
                run_workers(
                    modules=args.modules,
                    temporal_host=args.temporal_host,
                )
            )
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            sys.exit(0)
    else:
        # --- gRPC service mode (default) ---
        from .server import serve

        asyncio.run(serve())


if __name__ == "__main__":
    main()
