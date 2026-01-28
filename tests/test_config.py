"""
Tests for WorkerConfig and GardenerConfig.
"""

from contextworker.config import WorkerConfig, GardenerConfig


class TestGardenerConfig:
    """Test GardenerConfig defaults and validation."""

    def test_default_values(self):
        """Test GardenerConfig has correct defaults."""
        config = GardenerConfig()

        assert config.poll_interval == 900  # 15 min
        assert config.batch_size == 50
        assert config.parallel_batches == 2
        assert config.llm_timeout == 30.0
        assert config.retry_max == 3
        assert config.retry_base_delay == 1.0
        assert config.prompts_dir == ""
        assert config.tenant_id == ""

    def test_custom_values(self):
        """Test GardenerConfig with custom values."""
        config = GardenerConfig(
            poll_interval=600,
            batch_size=100,
            prompts_dir="/custom/prompts",
            tenant_id="test-tenant",
        )

        assert config.poll_interval == 600
        assert config.batch_size == 100
        assert config.prompts_dir == "/custom/prompts"
        assert config.tenant_id == "test-tenant"

    def test_no_business_defaults(self):
        """Ensure no business-specific defaults."""
        config = GardenerConfig()

        # Should NOT have hardcoded business values
        assert config.tenant_id == ""
        assert config.prompts_dir == ""
        assert "traverse" not in str(config).lower()


class TestWorkerConfig:
    """Test WorkerConfig defaults and environment loading."""

    def test_default_values(self):
        """Test WorkerConfig has correct defaults."""
        config = WorkerConfig()

        assert config.service_name == "contextworker"
        assert config.log_level == "INFO"
        assert config.temporal_host == "localhost:7233"
        assert isinstance(config.gardener, GardenerConfig)

    def test_nested_gardener_config(self):
        """Test nested GardenerConfig is properly initialized."""
        config = WorkerConfig()

        assert config.gardener.batch_size == 50
        assert config.gardener.poll_interval == 900

    def test_from_env_loads_defaults(self, monkeypatch):
        """Test from_env() returns config with defaults."""
        # Clear any existing env vars
        for key in [
            "SERVICE_NAME",
            "BRAIN_DATABASE_URL",
            "TEMPORAL_HOST",
        ]:
            monkeypatch.delenv(key, raising=False)

        config = WorkerConfig.from_env()

        assert config.service_name == "contextworker"
        assert config.temporal_host == "localhost:7233"

    def test_from_env_loads_custom_values(self, monkeypatch):
        """Test from_env() loads from environment."""
        monkeypatch.setenv("SERVICE_NAME", "custom-worker")
        monkeypatch.setenv("TEMPORAL_HOST", "temporal.prod:7233")
        monkeypatch.setenv("GARDENER_BATCH_SIZE", "200")
        monkeypatch.setenv("TENANT_ID", "prod-tenant")

        config = WorkerConfig.from_env()

        assert config.service_name == "custom-worker"
        assert config.temporal_host == "temporal.prod:7233"
        assert config.gardener.batch_size == 200
        assert config.gardener.tenant_id == "prod-tenant"
