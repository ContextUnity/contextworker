"""
ContextWorker - Temporal Worker for ContextUnity.

Entry point for running worker modules.
Modules are discovered from installed packages (e.g., contextcommerce).
"""

from __future__ import annotations

import asyncio
import argparse
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
    parser = argparse.ArgumentParser(
        description="ContextWorker - Temporal worker for ContextUnity"
    )
    parser.add_argument(
        "--modules",
        "-m",
        nargs="*",
        help="Modules to run (default: all discovered). E.g., --modules harvester gardener",
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

    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    # Discover modules from installed packages
    from .core.registry import get_registry

    registry = get_registry()
    registry.discover_plugins()

    # Show registered modules
    modules = registry.get_all_modules()
    if modules:
        logger.info("Registered modules:")
        for module in modules:
            status = "✓" if module.enabled else "✗"
            logger.info(f"  [{status}] {module.name} -> {module.queue}")
    else:
        logger.error("No modules discovered!")
        logger.error("Install contextcommerce or another module package.")
        sys.exit(1)

    # Run workers
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


if __name__ == "__main__":
    main()
