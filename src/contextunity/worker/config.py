"""
Configuration for contextunity.worker.

Single entry: .env is loaded only via this module (pydantic_settings env_file).
All service code must use get_config(); do not use os.getenv for worker settings.
"""

from typing import Optional

from contextunity.core import get_contextunit_logger
from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings


class WorkerConfig(BaseSettings):
    """Configuration for contextunity.worker.

    Single entry: only this config loads .env (service's own). All code must use get_config().
    """

    model_config = ConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Temporal
    temporal_host: str = Field(
        default="localhost:7233",
        description="Temporal server address",
    )
    temporal_namespace: str = Field(
        default="default",
        description="Temporal namespace",
    )

    # Service endpoints (env names match start script / project .env)
    brain_endpoint: str = Field(
        default="localhost:50051",
        description="contextunity.brain gRPC endpoint",
        validation_alias="CU_BRAIN_GRPC_URL",
    )
    worker_port: int = Field(
        default=50052,
        description="Worker gRPC port",
        validation_alias="WORKER_PORT",
    )
    worker_instance_name: str = Field(
        default="default",
        validation_alias="WORKER_INSTANCE_NAME",
    )
    worker_tenants: str = Field(
        default="",
        validation_alias="WORKER_TENANTS",
    )
    worker_modules: str = Field(
        default="",
        validation_alias="WORKER_MODULES",
    )
    worker_engine: str = Field(
        default="temporal",
        description="Execution engine: 'temporal' (default) or 'huey' (local)",
        validation_alias="WORKER_ENGINE",
    )

    # Logging
    log_level: str = Field(default="INFO")


# Singleton
_config: Optional[WorkerConfig] = None


def get_config() -> WorkerConfig:
    """Get or create the global config instance (single entry for config/env)."""
    global _config
    if _config is None:
        _config = WorkerConfig()
        _resolve_endpoints(_config)
    return _config


def _resolve_endpoints(cfg: WorkerConfig) -> None:
    """Resolve service endpoints once at startup (env → Redis → defaults)."""

    from contextunity.core.discovery import resolve_service_endpoint

    logger = get_contextunit_logger(__name__)

    cfg.brain_endpoint = resolve_service_endpoint(
        "brain",
        configured_host=cfg.brain_endpoint,
        default_host="localhost:50051",
    )

    logger.info("Worker service endpoints resolved: brain=%s", cfg.brain_endpoint)


__all__ = ["WorkerConfig", "get_config"]
