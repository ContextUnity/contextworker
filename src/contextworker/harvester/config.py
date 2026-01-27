"""
Harvester configuration.

Contains settings for:
- Gardener enrichment agent
- Batch tracking (Redis)
- Project-specific paths (ontology, prompts)
"""

from typing import Optional
from pydantic import BaseModel, Field


class GardenerConfig(BaseModel):
    """Configuration for Gardener enrichment agent."""

    poll_interval: int = Field(
        default=900, description="Seconds between queue checks (15 min)"
    )
    batch_size: int = Field(default=50, description="Items per LLM batch")
    parallel_batches: int = Field(default=2, description="Concurrent batches")

    # LLM call settings
    llm_timeout: float = Field(
        default=30.0, description="LLM request timeout in seconds"
    )
    retry_max: int = Field(default=3, description="Max retry attempts for LLM calls")
    retry_base_delay: float = Field(
        default=1.0, description="Base delay for exponential backoff"
    )

    log_path: Optional[str] = Field(
        default=None, description="Log file path, None=stdout"
    )


class BatchTrackerConfig(BaseModel):
    """Configuration for Redis-based batch tracking."""

    enabled: bool = Field(default=True, description="Enable Redis batch tracking")
    key_prefix: str = Field(default="gardener:batch:", description="Redis key prefix")
    batch_ttl_sec: int = Field(default=3600, description="Batch state TTL (1 hour)")


class HarvesterConfig(BaseModel):
    """Master configuration for Harvester module."""

    # Tenant (required, no default)
    tenant_id: str = Field(default="", description="Tenant ID for multi-tenant")

    # Database
    database_url: str = Field(default="", description="PostgreSQL URL for Commerce DB")

    # Redis for batch tracking
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis URL")

    # Project-specific paths (from PROJECT_DIR/harvester/)
    ontology_dir: str = Field(default="", description="Path to ontology JSON files")
    prompts_dir: str = Field(default="", description="Path to prompt templates")

    # Sub-configs
    gardener: GardenerConfig = Field(default_factory=GardenerConfig)
    batch_tracker: BatchTrackerConfig = Field(default_factory=BatchTrackerConfig)

    @classmethod
    def from_env(cls) -> "HarvesterConfig":
        """Load from environment variables."""
        import os

        return cls(
            tenant_id=os.getenv("TENANT_ID", ""),
            database_url=os.getenv("DATABASE_URL", "")
            or os.getenv("COMMERCE_DATABASE_URL", ""),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            ontology_dir=os.getenv("HARVESTER_ONTOLOGY_DIR", ""),
            prompts_dir=os.getenv("HARVESTER_PROMPTS_DIR", ""),
            gardener=GardenerConfig(
                poll_interval=int(os.getenv("GARDENER_POLL_INTERVAL_SEC", "900")),
                batch_size=int(os.getenv("GARDENER_BATCH_SIZE", "50")),
                parallel_batches=int(os.getenv("GARDENER_PARALLEL_BATCHES", "2")),
                llm_timeout=float(os.getenv("GARDENER_LLM_TIMEOUT", "30.0")),
                retry_max=int(os.getenv("GARDENER_RETRY_MAX", "3")),
                retry_base_delay=float(os.getenv("GARDENER_RETRY_BASE_DELAY", "1.0")),
                log_path=os.getenv("GARDENER_LOG_PATH"),
            ),
            batch_tracker=BatchTrackerConfig(
                enabled=os.getenv("BATCH_TRACKER_ENABLED", "true").lower() == "true",
                key_prefix=os.getenv("BATCH_TRACKER_PREFIX", "gardener:batch:"),
                batch_ttl_sec=int(os.getenv("BATCH_TRACKER_TTL_SEC", "3600")),
            ),
        )
