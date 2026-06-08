"""Tests for WorkerConfig."""

from __future__ import annotations

from contextunity.core.config import reset_core_config
from contextunity.worker.config import WorkerConfig, get_config, reset_config


class TestWorkerConfig:
    """Test WorkerConfig defaults and environment loading."""

    def test_brain_endpoint_default(self):
        """brain_endpoint property delegates to inherited brain_url."""
        config = WorkerConfig()
        assert config.brain_endpoint == "localhost:50051"
        assert config.brain_url == "localhost:50051"

    def test_custom_env_values(self, monkeypatch):
        """SharedConfig fields (temporal_host) loaded via load_service_config."""
        reset_config()
        reset_core_config()

        monkeypatch.setenv("TEMPORAL_HOST", "temporal.prod:7233")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("WORKER_PORT", "50099")

        config = get_config()

        assert config.temporal_host == "temporal.prod:7233"
        assert config.log_level == "DEBUG"
        assert config.port == 50099

    def test_worker_config_from_env(self, monkeypatch):
        """CU_BRAIN_GRPC_URL maps to brain_url (and brain_endpoint alias)."""
        reset_config()
        reset_core_config()

        monkeypatch.setenv("CU_BRAIN_GRPC_URL", "brain.remote:50051")
        monkeypatch.setenv("REDIS_URL", "redis://test:6379/1")

        config = get_config()
        assert config.brain_url == "brain.remote:50051"
        assert config.brain_endpoint == "brain.remote:50051"


class TestGetConfig:
    """Test get_config() singleton."""

    def test_returns_singleton(self):
        reset_config()
        reset_core_config()

        c1 = get_config()
        c2 = get_config()
        assert c1 is c2

    def test_reset_creates_new(self):
        reset_config()
        reset_core_config()

        c1 = get_config()
        reset_config()
        c2 = get_config()
        assert c1 is not c2
