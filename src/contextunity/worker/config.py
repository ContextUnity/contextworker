"""
Configuration for contextunity.worker.

Single entry: config loaded via load_service_config (env + YAML).
All service code must use get_config(); do not use os.getenv for worker settings.
"""

from contextunity.core import get_contextunit_logger
from contextunity.core.config import (
    ServiceConfig,
    ServiceConfigRegistry,
    load_service_config,
)
from pydantic import Field


class WorkerConfig(ServiceConfig):
    """Configuration for contextunity.worker.

    Inherits from ServiceConfig (→ SharedConfig):
    - temporal_host (from SharedConfig, env: TEMPORAL_HOST)
    - brain_url (from SharedConfig, env: CU_BRAIN_GRPC_URL)

    Worker-specific fields defined here.
    """

    # Temporal
    temporal_namespace: str = Field(
        default="default",
        description="Temporal namespace",
    )

    # Worker service
    port: int = 50052
    worker_instance_name: str = Field(
        default="default",
    )
    worker_tenants: str = Field(
        default="",
    )
    worker_modules: str = Field(
        default="",
    )
    worker_engine: str = Field(
        default="temporal",
        description="Execution engine: 'temporal' (default) or 'huey' (local)",
    )

    @property
    def brain_endpoint(self) -> str:
        """Alias for brain_url — backward compat for worker service code."""
        return self.brain_url


def _resolve_endpoints(config: WorkerConfig) -> WorkerConfig:
    """Return a config copy with runtime service endpoints resolved."""

    from contextunity.core.discovery import resolve_service_endpoint

    logger = get_contextunit_logger(__name__)

    brain_url = resolve_service_endpoint(
        "brain",
        configured_host=config.brain_url,
        default_host="localhost:50051",
    )
    data = config.model_dump()
    data["brain_url"] = brain_url

    logger.info("Worker service endpoints resolved: brain=%s", brain_url)
    return WorkerConfig.model_validate(data)


def load_config(config_path: str | None = None) -> WorkerConfig:
    """Load worker config through the unified config loader."""
    env_mappings = {
        "WORKER_INSTANCE_NAME": "worker_instance_name",
        "WORKER_TENANTS": "worker_tenants",
        "WORKER_MODULES": "worker_modules",
        "WORKER_ENGINE": "worker_engine",
        "TEMPORAL_NAMESPACE": "temporal_namespace",
    }

    cfg = load_service_config(
        WorkerConfig,
        "worker",
        env_mappings=env_mappings,
        config_path=config_path,
    )
    return _resolve_endpoints(cfg)


_registry = ServiceConfigRegistry(load_config)

get_config = _registry.get
reset_config = _registry.reset

__all__ = ["WorkerConfig", "get_config", "load_config", "reset_config"]
