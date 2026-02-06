"""
Configuration for ContextWorker.

Uses Pydantic for validation and environment loading.
"""

import os
from typing import Optional

from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings


class WorkerConfig(BaseSettings):
    """Configuration for ContextWorker.

    Only Temporal-related settings. Projects add their own config.
    """

    model_config = ConfigDict(
        env_prefix="",
        env_file=".env",
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

    # Logging
    log_level: str = Field(default="INFO")

    @classmethod
    def from_env(cls) -> "WorkerConfig":
        """Load configuration from environment variables."""
        return cls(
            temporal_host=os.getenv("TEMPORAL_HOST", "localhost:7233"),
            temporal_namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


# Singleton
_config: Optional[WorkerConfig] = None


def get_config() -> WorkerConfig:
    """Get or create the global config instance."""
    global _config
    if _config is None:
        _config = WorkerConfig.from_env()
    return _config


__all__ = ["WorkerConfig", "get_config"]
