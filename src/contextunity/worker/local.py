"""Local factory for ContextWorker gracefully degraded execution."""

import grpc
from contextunity.core import get_contextunit_logger, worker_pb2_grpc

from .config import get_config
from .service import WorkerService

logger = get_contextunit_logger(__name__)


async def create_local_worker() -> grpc.aio.Server:
    """Create a gracefully degraded local Worker service."""
    logger.info("Initializing Local Worker Service (SqliteHuey)")

    from .interceptors import WorkerPermissionInterceptor

    config = get_config()
    shield_url = config.shield_url
    logger.info("Local Worker: shield_url=%s", shield_url or "(disabled)")
    server = grpc.aio.server(interceptors=[WorkerPermissionInterceptor(shield_url=shield_url, config=config)])

    try:
        from pathlib import Path

        from huey import SqliteHuey

        db_path = Path("~/.contextunity/worker_local.sqlite3").expanduser()
        db_path.parent.mkdir(parents=True, exist_ok=True)

        huey_instance = SqliteHuey("contextunity-worker-local", filename=str(db_path))
        logger.info(f"SqliteHuey initialized at {db_path}")
    except ImportError:
        logger.warning("Huey not installed. Worker will run without a backend.")
        huey_instance = None

    from .engines.huey_engine import HueyEngine

    engine_override = HueyEngine(huey_instance=huey_instance)

    worker_service = WorkerService(engine_override=engine_override)

    _ = worker_pb2_grpc.add_WorkerServiceServicer_to_server(worker_service, server)
    _ = server.add_insecure_port(f"[::]:{config.port}")

    return server


if __name__ == "__main__":
    import asyncio

    from contextunity.core.logging import setup_logging

    setup_logging()

    async def _run() -> None:
        server = await create_local_worker()
        await server.start()
        print("Worker gRPC listening (local)")
        _ = await server.wait_for_termination()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass
