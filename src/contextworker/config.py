"""
Configuration for ContextWorker.

Single entry: .env is loaded only via this module (pydantic_settings env_file).
All service code must use get_config(); do not use os.getenv for worker settings.
"""

from typing import Optional

from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings


class WorkerConfig(BaseSettings):
    """Configuration for ContextWorker.

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
        description="ContextBrain gRPC endpoint",
        validation_alias="CONTEXT_BRAIN_URL",
    )
    worker_port: int = Field(
        default=50052,
        description="Worker gRPC port",
        validation_alias="WORKER_PORT",
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
    return _config


__all__ = ["WorkerConfig", "get_config"]
