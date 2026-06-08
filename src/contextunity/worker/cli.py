"""contextunity.worker CLI entry point."""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Annotated

import typer
from contextunity.core import get_contextunit_logger
from rich.console import Console

app = typer.Typer(
    name="contextworker",
    help="contextunity.worker — The Hands of ContextUnity",
    add_completion=False,
    invoke_without_command=True,
)
console = Console()
logger = get_contextunit_logger(__name__)


def setup_logging(level: str = "INFO") -> None:
    """Setup logging configuration."""
    numeric = getattr(logging, level.upper(), None)
    if not isinstance(numeric, int):
        numeric = logging.INFO
    logging.basicConfig(
        level=numeric,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@app.callback()
def main(
    ctx: typer.Context,
    temporal: Annotated[bool, typer.Option("--temporal", help="Start Temporal worker instead of gRPC service")] = False,
    modules: Annotated[
        list[str] | None, typer.Option("--modules", "-m", help="Temporal modules to run (default: all discovered)")
    ] = None,
    temporal_host: Annotated[
        str | None, typer.Option("--temporal-host", help="Temporal server address (default: TEMPORAL_HOST env)")
    ] = None,
    log_level: Annotated[str, typer.Option("--log-level", help="Log level")] = "INFO",
) -> None:
    """CLI entry point. Backwards-compatible argument routing."""
    if ctx.invoked_subcommand is not None:
        return

    if temporal:
        _run_temporal(modules, temporal_host, log_level)
    else:
        _run_serve()


@app.command("serve")
def serve() -> None:
    """Start the gRPC service."""
    _run_serve()


@app.command("temporal")
def run_temporal(
    modules: Annotated[list[str] | None, typer.Option("--modules", "-m", help="Temporal modules to run")] = None,
    temporal_host: Annotated[str | None, typer.Option("--temporal-host", help="Temporal server address")] = None,
    log_level: Annotated[str, typer.Option("--log-level", help="Log level")] = "INFO",
) -> None:
    """Start Temporal worker mode."""
    _run_temporal(modules, temporal_host, log_level)


def _run_serve() -> None:
    from .server import serve as grpc_serve

    asyncio.run(grpc_serve())


def _run_temporal(modules: list[str] | None, temporal_host: str | None, log_level: str) -> None:
    setup_logging(log_level)

    from .core.registry import get_registry

    registry = get_registry()
    registry.discover_plugins()

    all_modules = registry.get_all_modules()
    if all_modules:
        logger.info("Registered modules:")
        for module in all_modules:
            status = "✓" if module.enabled else "✗"
            logger.info("  [%s] %s -> %s", status, module.name, module.queue)
    else:
        logger.warning("No modules discovered. Register modules before running.")
        sys.exit(1)

    from .core.worker import run_workers

    try:
        asyncio.run(
            run_workers(
                modules=modules,
                temporal_host=temporal_host,
            )
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)


if __name__ == "__main__":
    app()
