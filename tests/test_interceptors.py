"""Tests for Worker permission interceptor."""

from __future__ import annotations

import contextunity.core.worker_pb2 as worker_pb2
from contextunity.worker.interceptors import (
    RPC_PERMISSION_MAP,
    WorkerPermissionInterceptor,
)

# ── RPC_PERMISSION_MAP completeness ──


class TestRpcPermissionMap:
    def test_workflow_rpcs_mapped(self):
        assert "StartWorkflow" in RPC_PERMISSION_MAP
        assert "GetTaskStatus" in RPC_PERMISSION_MAP
        assert "ExecuteCode" in RPC_PERMISSION_MAP

    def test_execute_ops_require_execute_permission(self):
        execute_rpcs = ["StartWorkflow", "ExecuteCode"]
        for rpc in execute_rpcs:
            perm = RPC_PERMISSION_MAP[rpc]
            assert "worker:execute" in perm, f"{rpc} should require worker:execute, got {perm}"

    def test_read_ops_require_read_permission(self):
        assert "worker:read" in RPC_PERMISSION_MAP["GetTaskStatus"]

    def test_all_permissions_are_namespaced(self):
        for rpc, perm in RPC_PERMISSION_MAP.items():
            assert ":" in perm, f"{rpc} permission '{perm}' must be namespaced (e.g. worker:read)"


# ── Proto-driven coverage ──


def _get_proto_rpc_names() -> set[str]:
    """Extract all RPC method names from WorkerService descriptor."""
    service = worker_pb2.DESCRIPTOR.services_by_name.get("WorkerService")
    if service is None:
        raise RuntimeError("WorkerService not found in worker_pb2.DESCRIPTOR")
    return {method.name for method in service.methods}


class TestProtoPermissionCoverage:
    """Proto-driven: every RPC in worker.proto must be in RPC_PERMISSION_MAP."""

    def test_every_proto_method_in_map(self):
        proto_methods = _get_proto_rpc_names()
        missing = proto_methods - set(RPC_PERMISSION_MAP.keys())
        assert not missing, f"These WorkerService RPCs are missing from RPC_PERMISSION_MAP: {sorted(missing)}"

    def test_no_phantom_entries_in_map(self):
        proto_methods = _get_proto_rpc_names()
        phantom = set(RPC_PERMISSION_MAP.keys()) - proto_methods
        assert not phantom, f"These RPC_PERMISSION_MAP entries have no matching proto RPC: {sorted(phantom)}"

    def test_map_and_proto_in_sync(self):
        proto_methods = _get_proto_rpc_names()
        assert set(RPC_PERMISSION_MAP.keys()) == proto_methods


# ── WorkerPermissionInterceptor constructor ──


class TestWorkerPermissionInterceptor:
    def test_instantiates(self):
        interceptor = WorkerPermissionInterceptor()
        assert interceptor._service_name == "Worker"
        assert interceptor._rpc_map == RPC_PERMISSION_MAP
