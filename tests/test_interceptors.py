"""Tests for Worker permission interceptor."""

from __future__ import annotations

from contextcore.security import EnforcementMode
from contextworker.interceptors import (
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


# ── WorkerPermissionInterceptor constructor ──


class TestWorkerPermissionInterceptor:
    def test_off_by_default(self):
        """Default enforcement should be OFF."""
        interceptor = WorkerPermissionInterceptor(enforcement=EnforcementMode.OFF)
        assert interceptor._mode == EnforcementMode.OFF

    def test_enforce_mode(self):
        interceptor = WorkerPermissionInterceptor(enforcement=EnforcementMode.ENFORCE)
        assert interceptor._mode == EnforcementMode.ENFORCE

    def test_warn_mode(self):
        interceptor = WorkerPermissionInterceptor(enforcement=EnforcementMode.WARN)
        assert interceptor._mode == EnforcementMode.WARN

    def test_service_name_is_worker(self):
        interceptor = WorkerPermissionInterceptor(enforcement=EnforcementMode.OFF)
        assert interceptor._service_name == "Worker"

    def test_rpc_map_is_loaded(self):
        interceptor = WorkerPermissionInterceptor(enforcement=EnforcementMode.OFF)
        assert interceptor._rpc_map == RPC_PERMISSION_MAP

    def test_defaults_to_env(self, monkeypatch):
        """Without explicit enforcement, reads SECURITY_ENFORCEMENT env."""
        monkeypatch.setenv("SECURITY_ENFORCEMENT", "warn")
        interceptor = WorkerPermissionInterceptor()
        assert interceptor._mode == EnforcementMode.WARN
