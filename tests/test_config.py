"""Tests for WorkerConfig."""

from __future__ import annotations

from contextworker.config import WorkerConfig, get_config


class TestWorkerConfig:
    """Test WorkerConfig defaults and environment loading."""

    def test_default_values(self):
        config = WorkerConfig()

        assert config.log_level == "INFO"
        assert config.temporal_host == "localhost:7233"
        assert config.temporal_namespace == "default"
        assert config.worker_port == 50052

    def test_brain_endpoint_default(self):
        config = WorkerConfig()
        assert config.brain_endpoint == "localhost:50051"

    def test_custom_env_values(self, monkeypatch):
        """WorkerConfig reads from environment variables."""
        monkeypatch.setenv("TEMPORAL_HOST", "temporal.prod:7233")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("WORKER_PORT", "50099")

        # Reset singleton so fresh config is created
        import contextworker.config as cfg

        monkeypatch.setattr(cfg, "_config", None)

        config = WorkerConfig()

        assert config.temporal_host == "temporal.prod:7233"
        assert config.log_level == "DEBUG"
        assert config.worker_port == 50099

    def test_brain_endpoint_from_env(self, monkeypatch):
        """CONTEXT_BRAIN_URL env var maps to brain_endpoint."""
        monkeypatch.setenv("CONTEXT_BRAIN_URL", "brain.remote:50051")

        config = WorkerConfig()
        assert config.brain_endpoint == "brain.remote:50051"


class TestGetConfig:
    """Test get_config() singleton."""

    def test_returns_singleton(self, monkeypatch):
        import contextworker.config as cfg

        monkeypatch.setattr(cfg, "_config", None)

        c1 = get_config()
        c2 = get_config()
        assert c1 is c2

    def test_reset_creates_new(self, monkeypatch):
        import contextworker.config as cfg

        monkeypatch.setattr(cfg, "_config", None)

        c1 = get_config()
        monkeypatch.setattr(cfg, "_config", None)
        c2 = get_config()
        assert c1 is not c2
