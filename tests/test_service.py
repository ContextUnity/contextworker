"""
Tests for WorkerService gRPC service.
"""

from unittest.mock import patch

from contextunity.worker.service import WorkerService


class TestWorkerServiceInit:
    """Test WorkerService initialization."""

    def test_default_temporal_host(self):
        """Verify default Temporal host."""
        service = WorkerService()
        assert service.temporal_host == "localhost:7233"

    def test_custom_temporal_host(self):
        """Verify custom Temporal host."""
        service = WorkerService(temporal_host="temporal.prod:7233")
        assert service.temporal_host == "temporal.prod:7233"

    def test_initializes_temporal_engine(self):
        """Verify Temporal engine initialized by default."""
        with patch("contextunity.worker.service.get_config") as mock_config:
            mock_config.return_value.worker_engine = "temporal"
            mock_config.return_value.temporal_host = "temporal.prod:7233"
            mock_config.return_value.brain_endpoint = "brain:50051"

            service = WorkerService(temporal_host="temporal.prod:7233")
            assert hasattr(service, "engine")
            assert service.temporal_host == "temporal.prod:7233"

    def test_initializes_huey_engine(self):
        """Verify Huey engine initialized when configured."""
        with patch("contextunity.worker.service.get_config") as mock_config:
            mock_config.return_value.worker_engine = "huey"
            mock_config.return_value.brain_endpoint = "brain:50051"

            service = WorkerService()
            assert hasattr(service, "engine")
            assert service.engine.__class__.__name__ == "HueyEngine"
