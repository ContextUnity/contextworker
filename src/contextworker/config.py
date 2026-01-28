"""
Configuration for ContextWorker agents.

Uses Pydantic for validation and environment loading.
Follows ContextCore patterns for consistency.
"""

import os
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings


class GardenerConfig(BaseModel):
    """Configuration for Gardener agent (commerce enrichment)."""

    poll_interval: int = Field(
        default=900, description="Seconds between queue checks (15 min)"
    )
    batch_size: int = Field(default=50, description="Items per LLM batch")
    parallel_batches: int = Field(default=2, description="Concurrent batches")
    log_path: Optional[str] = Field(
        default=None, description="Log file path, None=stdout"
    )

    # LLM call settings
    llm_timeout: float = Field(
        default=30.0, description="LLM request timeout in seconds"
    )
    retry_max: int = Field(default=3, description="Max retry attempts for LLM calls")
    retry_base_delay: float = Field(
        default=1.0, description="Base delay for exponential backoff"
    )

    # Commerce-specific paths (passed to Router)
    prompts_dir: str = Field(default="", description="Path to prompt templates")
    tenant_id: str = Field(default="", description="Tenant ID for multi-tenant")


class WorkerConfig(BaseSettings):
    """Master configuration for ContextWorker.

    Loads from environment variables with CONTEXTWORKER_ prefix.
    """

    model_config = ConfigDict(
        env_prefix="",  # No prefix, use exact names
        env_file=".env",
        extra="ignore",
    )

    # Service identity
    service_name: str = Field(default="contextworker")
    service_version: str = Field(default="0.1.0")
    log_level: str = Field(default="INFO")

    # Database connections
    brain_database_url: str = Field(default="", description="Brain PostgreSQL URL")
    commerce_database_url: str = Field(
        default="", description="Commerce PostgreSQL URL (read-only)"
    )

    # ContextRouter (LLM)
    router_url: str = Field(
        default="http://localhost:8080", description="Router HTTP endpoint"
    )
    router_api_key: str = Field(default="", description="Router API key")
    router_model: str = Field(
        default="google/gemini-2.5-flash-lite", description="Default LLM model"
    )

    # Temporal (for Harvester workflows)
    temporal_host: str = Field(default="localhost:7233")

    # Agent configs
    gardener: GardenerConfig = Field(default_factory=GardenerConfig)

    @classmethod
    def from_env(cls) -> "WorkerConfig":
        """Load configuration from environment variables."""
        return cls(
            service_name=os.getenv("SERVICE_NAME", "contextworker"),
            service_version=os.getenv("SERVICE_VERSION", "0.1.0"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            brain_database_url=os.getenv("BRAIN_DATABASE_URL", ""),
            commerce_database_url=os.getenv("COMMERCE_DATABASE_URL", ""),
            router_url=os.getenv("CONTEXT_ROUTER_URL", "http://localhost:8080"),
            router_api_key=os.getenv("CONTEXT_ROUTER_API_KEY", ""),
            router_model=os.getenv(
                "CONTEXT_ROUTER_MODEL", "google/gemini-2.5-flash-lite"
            ),
            temporal_host=os.getenv("TEMPORAL_HOST", "localhost:7233"),
            gardener=GardenerConfig(
                poll_interval=int(os.getenv("GARDENER_POLL_INTERVAL_SEC", "900")),
                batch_size=int(os.getenv("GARDENER_BATCH_SIZE", "50")),
                parallel_batches=int(os.getenv("GARDENER_PARALLEL_BATCHES", "2")),
                llm_timeout=float(os.getenv("GARDENER_LLM_TIMEOUT", "30.0")),
                retry_max=int(os.getenv("GARDENER_RETRY_MAX", "3")),
                retry_base_delay=float(os.getenv("GARDENER_RETRY_BASE_DELAY", "1.0")),
                log_path=os.getenv("GARDENER_LOG_PATH"),
                prompts_dir=os.getenv("GARDENER_PROMPTS_DIR", ""),
                tenant_id=os.getenv("TENANT_ID", ""),
            ),
        )
