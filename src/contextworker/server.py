"""gRPC server bootstrap for ContextWorker.

Configures interceptors, security, TLS, and graceful shutdown.
"""

from __future__ import annotations

import asyncio

import grpc

# Fail-closed: service MUST NOT start without gRPC contracts.
from contextcore import get_context_unit_logger, worker_pb2_grpc

from .config import get_config

logger = get_context_unit_logger(__name__)


async def serve() -> None:
    """Start the gRPC server for Worker Service."""
    from contextcore import (
        get_context_unit_logger,
        load_shared_config_from_env,
        setup_logging,
    )

    config = load_shared_config_from_env()
    setup_logging(config=config, service_name="contextworker")
    svc_logger = get_context_unit_logger(__name__)

    # Build interceptor list: security + domain permission checks
    from .interceptors import WorkerPermissionInterceptor

    interceptors = []
    interceptors.append(WorkerPermissionInterceptor(shield_url=config.shield_url))

    server = grpc.aio.server(
        interceptors=interceptors,
        options=(("grpc.so_reuseport", 1 if config.grpc_reuse_port else 0),),
    )

    # Register Worker Service
    from .service import WorkerService

    worker_service = WorkerService()
    worker_pb2_grpc.add_WorkerServiceServicer_to_server(worker_service, server)
    svc_logger.info("Worker Service registered")

    port = get_config().worker_port

    from contextcore.grpc_utils import graceful_shutdown, start_grpc_server

    heartbeat_task = await start_grpc_server(server, "worker", port)

    await graceful_shutdown(server, "Worker", heartbeat_task=heartbeat_task)


if __name__ == "__main__":
    asyncio.run(serve())


__all__ = ["serve"]
