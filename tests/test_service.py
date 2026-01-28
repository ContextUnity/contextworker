"""
Tests for WorkerService gRPC service.
"""

import pytest
from unittest.mock import AsyncMock, patch
from contextworker.service import WorkerService


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

    def test_client_starts_as_none(self):
        """Verify client is None initially."""
        service = WorkerService()
        assert service._client is None


class TestWorkerServiceGetClient:
    """Test WorkerService.get_client() method."""

    @pytest.mark.asyncio
    async def test_get_client_connects_on_first_call(self):
        """Verify client connects on first call."""
        service = WorkerService()

        with patch("contextworker.service.Client") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.connect = AsyncMock(return_value=mock_client)

            result = await service.get_client()

            mock_client_class.connect.assert_called_once_with("localhost:7233")
            assert result == mock_client

    @pytest.mark.asyncio
    async def test_get_client_reuses_connection(self):
        """Verify client is reused on subsequent calls."""
        service = WorkerService()

        with patch("contextworker.service.Client") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.connect = AsyncMock(return_value=mock_client)

            # First call
            result1 = await service.get_client()
            # Second call
            result2 = await service.get_client()

            # Should only connect once
            mock_client_class.connect.assert_called_once()
            assert result1 == result2
