"""
Tests for WorkerService gRPC service.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import grpc
import pytest
from contextunity.worker.service import WorkerService


class TestWorkerServiceInit:
    """Test WorkerService initialization."""

    def test_default_temporal_host(self, monkeypatch):
        """Verify default Temporal host."""
        monkeypatch.delenv("WORKER_TEMPORAL_HOST", raising=False)
        with patch("contextunity.worker.service.get_config") as mock_config:
            mock_config.return_value.worker_engine = "temporal"
            mock_config.return_value.temporal_host = "localhost:7233"
            mock_config.return_value.brain_endpoint = "localhost:50051"
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


class _FakeServicerContext:
    """Minimal ``GrpcServicerContext`` stand-in for handler unit tests."""

    def __init__(self) -> None:
        self.code: object | None = None
        self.details: str | None = None

    def set_trailing_metadata(self, metadata: tuple[tuple[str, str], ...]) -> None:
        _ = metadata

    async def abort(self, code: object, details: str) -> None:
        _ = code, details

    def set_code(self, code: object) -> None:
        self.code = code

    def set_details(self, details: str) -> None:
        self.details = details

    def invocation_metadata(self) -> tuple[tuple[str, str], ...]:
        return ()


class TestWorkerServiceTenantBinding:
    @pytest.mark.asyncio
    async def test_get_task_status_requires_tenant_id(self):
        """Verify GetTaskStatus aborts when tenant_id cannot be resolved."""
        service = WorkerService.__new__(WorkerService)
        service.engine = MagicMock()

        unit = MagicMock()
        unit.payload = {"workflow_id": "wf-1"}
        unit.security = None
        unit.trace_id = uuid4()

        token = MagicMock()
        token.allowed_tenants = ()

        context = _FakeServicerContext()

        with (
            patch("contextunity.worker.service.parse_unit", return_value=unit),
            patch("contextunity.worker.service._get_verified_token", return_value=token),
            patch("contextunity.worker.service._authorize_worker"),
        ):
            await service.GetTaskStatus(object(), context)

        assert context.code == grpc.StatusCode.PERMISSION_DENIED

    @pytest.mark.asyncio
    async def test_get_task_status_authorizes_with_tenant(self):
        service = WorkerService.__new__(WorkerService)
        service.engine = MagicMock()
        service.engine.get_task_status = AsyncMock(return_value={"status": "running"})

        unit = MagicMock()
        unit.payload = {"workflow_id": "wf-1", "tenant_id": "tenant-a"}
        unit.security = None
        unit.trace_id = "trace-1"

        token = MagicMock()
        context = MagicMock()

        with (
            patch("contextunity.worker.service.parse_unit", return_value=unit),
            patch("contextunity.worker.service._get_verified_token", return_value=token),
            patch("contextunity.worker.service._authorize_worker") as authorize,
            patch("contextunity.worker.service.make_response", return_value=MagicMock()),
        ):
            await service.GetTaskStatus(object(), context)

        authorize.assert_called_once_with(
            context,
            token,
            permission="worker:read",
            rpc_name="GetTaskStatus",
            tenant_id="tenant-a",
        )

    @pytest.mark.asyncio
    async def test_register_schedules_authorizes_with_tenant(self):
        service = WorkerService.__new__(WorkerService)
        service.engine = MagicMock()
        service.engine.register_schedules = AsyncMock(return_value=1)

        unit = MagicMock()
        unit.payload = {
            "project_id": "proj-a",
            "tenant_id": "tenant-a",
            "schedules": [],
        }
        unit.trace_id = "trace-1"

        token = MagicMock()
        context = MagicMock()

        with (
            patch("contextunity.worker.service.parse_unit", return_value=unit),
            patch("contextunity.worker.service._get_verified_token", return_value=token),
            patch("contextunity.worker.service._authorize_worker") as authorize,
            patch("contextunity.worker.service.make_response", return_value=MagicMock()),
        ):
            await service.RegisterSchedules(object(), context)

        authorize.assert_called_once_with(
            context,
            token,
            permission="worker:execute",
            rpc_name="RegisterSchedules",
            tenant_id="tenant-a",
        )
