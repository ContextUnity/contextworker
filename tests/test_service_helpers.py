"""Tests for Worker service helper functions.

Zero-mock tests for SPOT tenant resolution and error response factory.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from contextunity.core import ContextUnit
from contextunity.core.exceptions import SecurityError
from contextunity.worker.helpers import worker_error_response_factory
from contextunity.worker.service import _resolve_tenant_id

# ── Fixtures ──────────────────────────────────────────────────────


def _token(tenants: tuple[str, ...] = ()) -> SimpleNamespace:
    t = SimpleNamespace()
    t.allowed_tenants = tenants
    return t


# ═══════════════════════════════════════════════════════════════════
# _resolve_tenant_id — SPOT rule
# ═══════════════════════════════════════════════════════════════════


class TestResolveTenantId:
    """Token is single source of truth for tenant."""

    def test_payload_matches_token(self):
        assert _resolve_tenant_id(None, _token(("acme",)), "acme") == "acme"

    def test_payload_not_in_token_rejected(self):
        with pytest.raises(SecurityError, match="SPOT violation"):
            _resolve_tenant_id(None, _token(("acme",)), "evil")

    def test_no_payload_uses_first_tenant(self):
        assert _resolve_tenant_id(None, _token(("acme", "corp")), None) == "acme"

    def test_no_payload_no_tenants_rejected(self):
        with pytest.raises(SecurityError, match="^Cannot resolve tenant_id"):
            _resolve_tenant_id(None, _token(()), None)

    def test_payload_accepted_when_token_has_no_tenants(self):
        """Token without allowed_tenants + payload tenant → accepted."""
        assert _resolve_tenant_id(None, _token(()), "legacy") == "legacy"

    def test_multi_tenant_selection(self):
        token = _token(("a", "b", "c"))
        assert _resolve_tenant_id(None, token, "b") == "b"

    def test_empty_string_payload_treated_as_absent(self):
        """Empty string is falsy → falls through to token."""
        assert _resolve_tenant_id(None, _token(("acme",)), "") == "acme"


# ═══════════════════════════════════════════════════════════════════
# _worker_error_response_factory
# ═══════════════════════════════════════════════════════════════════


class TestErrorResponseFactory:
    """Error type mapping for gRPC error responses."""

    @staticmethod
    def _parse_response(error: Exception) -> dict:
        """Call factory and parse response ContextUnit payload."""
        response = worker_error_response_factory(None, None, error)
        unit = ContextUnit.from_protobuf(response)
        return unit.payload

    def test_security_error_hides_details(self):
        """SecurityError → generic 'Permission denied' (never leak internals)."""
        payload = self._parse_response(SecurityError("tenant X not allowed"))
        assert payload["error"] == "Permission denied"
        assert payload["error_type"] == "permission_denied"

    def test_value_error_maps_to_validation(self):
        payload = self._parse_response(ValueError("bad input"))
        assert payload["error_type"] == "validation"
        assert "bad input" in payload["error"]

    def test_permission_error_maps_to_denied(self):
        payload = self._parse_response(PermissionError("no access"))
        assert payload["error_type"] == "permission_denied"
        assert payload["error"] == "Permission denied"

    def test_generic_error_includes_type_name(self):
        payload = self._parse_response(RuntimeError("boom"))
        assert payload["error_type"] == "RuntimeError"
        assert "RuntimeError" in payload["error"]
