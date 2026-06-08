"""
Worker Module Registry.
Handles registration and discovery of worker modules.
Modules are discovered from configured or built-in Python packages.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from contextunity.core import get_contextunit_logger
from contextunity.worker.types import ActivityCallable, WorkflowClass

logger = get_contextunit_logger(__name__)


@dataclass
class ModuleConfig:
    """Configuration for a registered worker module."""

    name: str
    queue: str
    workflows: list[WorkflowClass] = field(default_factory=list)
    activities: list[ActivityCallable] = field(default_factory=list)
    enabled: bool = True


class WorkerRegistry:
    """Registry for worker modules.

    Modules register themselves with:
    - name: unique identifier
    - queue: Temporal task queue
    - workflows: list of workflow classes
    - activities: list of activity functions
    """

    def __init__(self) -> None:
        """Initialize the worker registry."""
        self._modules: dict[str, ModuleConfig] = {}
        self._discovered: bool = False

    def register(
        self,
        name: str,
        queue: str,
        workflows: list[WorkflowClass] | None = None,
        activities: list[ActivityCallable] | None = None,
    ) -> None:
        """Register a worker module."""
        if name in self._modules:
            logger.warning("Module %s already registered, skipping", name)
            return

        self._modules[name] = ModuleConfig(
            name=name,
            queue=queue,
            workflows=workflows or [],
            activities=activities or [],
        )
        logger.info("Registered module: %s (queue=%s)", name, queue)

    def get_module(self, name: str) -> ModuleConfig | None:
        """Get a registered module by name."""
        return self._modules.get(name)

    def get_all_modules(self) -> list[ModuleConfig]:
        """Get all registered modules."""
        return list(self._modules.values())

    def get_enabled_modules(self) -> list[ModuleConfig]:
        """Get all enabled modules."""
        return [m for m in self._modules.values() if m.enabled]

    def get_queues(self) -> dict[str, list[ModuleConfig]]:
        """Get unique queues and their modules."""
        queues: dict[str, list[ModuleConfig]] = {}
        for module in self.get_enabled_modules():
            if module.queue not in queues:
                queues[module.queue] = []
            queues[module.queue].append(module)
        return queues

    def disable_module(self, name: str) -> None:
        """Disable a module."""
        if name in self._modules:
            self._modules[name].enabled = False

    def enable_module(self, name: str) -> None:
        """Enable a module."""
        if name in self._modules:
            self._modules[name].enabled = True

    def discover_plugins(self) -> None:
        """Discover and register modules from installed packages."""
        if self._discovered:
            return

        self._discovered = True

        known_packages = [
            "contextunity.worker.jobs",
        ]

        from contextunity.worker.config import get_config

        if env_modules := get_config().worker_modules:
            custom = [m.strip() for m in env_modules.split(",") if m.strip()]
            known_packages = custom + known_packages

        discovered_any = False
        for package in known_packages:
            try:
                import importlib

                mod = importlib.import_module(package)
                register_fn = getattr(mod, "register_all", None)
                if callable(register_fn):
                    _ = register_fn(self)
                    logger.info("Discovered modules from: %s", package)
                    discovered_any = True
            except ImportError:
                continue

        if not discovered_any:
            logger.warning(
                "No worker modules discovered. Register built-ins or set WORKER_MODULES.",
            )


_registry: WorkerRegistry | None = None


def get_registry() -> WorkerRegistry:
    """Get or create the global worker registry."""
    global _registry
    if _registry is None:
        _registry = WorkerRegistry()
    return _registry
