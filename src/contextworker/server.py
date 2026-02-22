"""gRPC server bootstrap for ContextWorker.

Configures interceptors, security, TLS, and graceful shutdown.
"""

from __future__ import annotations

import asyncio
import signal

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
    from contextcore.security import get_security_interceptors, shield_status

    config = load_shared_config_from_env()
    setup_logging(config=config, service_name="contextworker")
    svc_logger = get_context_unit_logger(__name__)

    # Build interceptor list: security + domain permission checks
    from .interceptors import WorkerPermissionInterceptor

    interceptors = list(get_security_interceptors())
    interceptors.append(WorkerPermissionInterceptor())

    server = grpc.aio.server(interceptors=interceptors)

    # Log security status
    sec = shield_status()
    sec_log = svc_logger.info if sec["security_enabled"] else svc_logger.warning
    sec_log(
        "Security: enabled=%s, shield=%s",
        sec["security_enabled"],
        "active" if sec["shield_active"] else "not installed",
    )

    # Register Worker Service
    from .service import WorkerService

    worker_service = WorkerService()
    worker_pb2_grpc.add_WorkerServiceServicer_to_server(worker_service, server)
    svc_logger.info("Worker Service registered")

    port = get_config().worker_port

    from contextcore.grpc_utils import create_server_credentials

    tls_creds = create_server_credentials()
    if tls_creds:
        server.add_secure_port(f"[::]:{port}", tls_creds)
        svc_logger.info("Worker Service starting on :%s with TLS", port)
    else:
        server.add_insecure_port(f"[::]:{port}")
        svc_logger.info("Worker Service starting on :%s (ContextUnit Protocol)", port)
    await server.start()

    # Register in Redis for service discovery
    import os

    from contextcore import register_service

    instance_name = os.getenv("WORKER_INSTANCE_NAME", "default")
    tenants_raw = os.getenv("WORKER_TENANTS", "")
    tenants = [t.strip() for t in tenants_raw.split(",") if t.strip()] if tenants_raw else []

    heartbeat_task = await register_service(
        service="worker",
        instance=instance_name,
        endpoint=f"localhost:{port}",
        tenants=tenants,
        metadata={"port": int(port)},
    )

    # Graceful shutdown on SIGINT/SIGTERM
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _shutdown_handler():
        svc_logger.info("Shutdown signal received, stopping Worker...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown_handler)

    await stop_event.wait()
    svc_logger.info("Stopping gRPC server (5s grace)...")
    await server.stop(grace=5)
    if heartbeat_task:
        heartbeat_task.cancel()
    svc_logger.info("Worker server stopped.")


if __name__ == "__main__":
    asyncio.run(serve())


__all__ = ["serve"]
