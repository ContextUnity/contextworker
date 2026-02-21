"""
Tests for WorkerRegistry.
"""

from contextworker.core.registry import ModuleConfig, WorkerRegistry, get_registry


class TestWorkerRegistry:
    """Test WorkerRegistry module registration."""

    def test_register_module(self):
        """Verify register() adds a module to the registry."""
        registry = WorkerRegistry()
        registry.register(name="test-mod", queue="test-queue", workflows=[], activities=[])

        mod = registry.get_module("test-mod")
        assert mod is not None
        assert mod.name == "test-mod"
        assert mod.queue == "test-queue"

    def test_register_duplicate_skipped(self):
        """Verify duplicate registration is silently skipped."""
        registry = WorkerRegistry()
        registry.register(name="dup", queue="q1")
        registry.register(name="dup", queue="q2")  # should be ignored

        mod = registry.get_module("dup")
        assert mod.queue == "q1"

    def test_get_all_modules(self):
        """Verify get_all_modules returns all registered."""
        registry = WorkerRegistry()
        registry.register(name="a", queue="qa")
        registry.register(name="b", queue="qb")

        all_mods = registry.get_all_modules()
        assert len(all_mods) == 2
        names = {m.name for m in all_mods}
        assert names == {"a", "b"}

    def test_get_enabled_modules(self):
        """Verify enable/disable filtering works."""
        registry = WorkerRegistry()
        registry.register(name="on", queue="q")
        registry.register(name="off", queue="q")
        registry.disable_module("off")

        enabled = registry.get_enabled_modules()
        assert len(enabled) == 1
        assert enabled[0].name == "on"

    def test_get_queues(self):
        """Verify get_queues groups modules by queue."""
        registry = WorkerRegistry()
        registry.register(name="a", queue="shared")
        registry.register(name="b", queue="shared")
        registry.register(name="c", queue="solo")

        queues = registry.get_queues()
        assert len(queues) == 2
        assert len(queues["shared"]) == 2
        assert len(queues["solo"]) == 1

    def test_get_module_not_found(self):
        """Verify get_module returns None for unknown."""
        registry = WorkerRegistry()
        assert registry.get_module("nope") is None

    def test_enable_module(self):
        """Verify enable_module re-enables a disabled module."""
        registry = WorkerRegistry()
        registry.register(name="x", queue="q")
        registry.disable_module("x")
        registry.enable_module("x")

        mod = registry.get_module("x")
        assert mod.enabled is True


class TestModuleConfig:
    """Test ModuleConfig dataclass."""

    def test_defaults(self):
        """Verify default values."""
        mc = ModuleConfig(name="test", queue="q")
        assert mc.workflows == []
        assert mc.activities == []
        assert mc.enabled is True


class TestGetRegistry:
    """Test global registry singleton."""

    def test_returns_same_instance(self):
        """Verify get_registry returns singleton."""
        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2
