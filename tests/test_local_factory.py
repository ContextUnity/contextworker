"""Tests for local Worker service factory wiring."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_local_worker_passes_config_to_permission_interceptor(monkeypatch):
    from contextunity.worker import interceptors, local

    cfg = SimpleNamespace(shield_url="shield.local:50054", port=55052)
    seen = {}

    class FakeInterceptor:
        def __init__(self, *, shield_url, config):
            seen["shield_url"] = shield_url
            seen["config"] = config

    class FakeServer:
        def __init__(self, *, interceptors):
            seen["interceptors"] = interceptors

        def add_insecure_port(self, endpoint):
            seen["endpoint"] = endpoint
            return 1

    def fake_worker_service(*, engine_override):
        seen["engine_override"] = engine_override
        return object()

    monkeypatch.setattr(local, "get_config", lambda: cfg)
    monkeypatch.setattr(interceptors, "WorkerPermissionInterceptor", FakeInterceptor)
    monkeypatch.setattr(local.grpc.aio, "server", lambda *, interceptors: FakeServer(interceptors=interceptors))
    monkeypatch.setattr(local, "WorkerService", fake_worker_service)
    monkeypatch.setattr(local.worker_pb2_grpc, "add_WorkerServiceServicer_to_server", lambda service, server: None)
    monkeypatch.setitem(sys.modules, "huey", ModuleType("huey"))

    server = await local.create_local_worker()

    assert isinstance(server, FakeServer)
    assert seen["shield_url"] == "shield.local:50054"
    assert seen["config"] is cfg
    assert seen["endpoint"] == "[::]:55052"
    assert seen["engine_override"] is not None
