"""
Worker Module Registry.

Handles registration and discovery of worker modules.
Modules are discovered from installed packages (e.g., contextcommerce).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


@dataclass
class ModuleConfig:
    """Configuration for a registered worker module."""

    name: str
    queue: str
    workflows: List[Type] = field(default_factory=list)
    activities: List[Callable] = field(default_factory=list)
    enabled: bool = True


class WorkerRegistry:
    """Registry for worker modules.

    Modules register themselves with:
    - name: unique identifier
    - queue: Temporal task queue
    - workflows: list of workflow classes
    - activities: list of activity functions
    """

    def __init__(self):
        self._modules: Dict[str, ModuleConfig] = {}
        self._discovered: bool = False

    def register(
        self,
        name: str,
        queue: str,
        workflows: List[Type] = None,
        activities: List[Callable] = None,
    ) -> None:
        """Register a worker module."""
        if name in self._modules:
            logger.warning(f"Module {name} already registered, skipping")
            return

        self._modules[name] = ModuleConfig(
            name=name,
            queue=queue,
            workflows=workflows or [],
            activities=activities or [],
        )
        logger.info(f"Registered module: {name} (queue={queue})")

    def get_module(self, name: str) -> Optional[ModuleConfig]:
        """Get a registered module by name."""
        return self._modules.get(name)

    def get_all_modules(self) -> List[ModuleConfig]:
        """Get all registered modules."""
        return list(self._modules.values())

    def get_enabled_modules(self) -> List[ModuleConfig]:
        """Get all enabled modules."""
        return [m for m in self._modules.values() if m.enabled]

    def get_queues(self) -> Dict[str, List[ModuleConfig]]:
        """Get unique queues and their modules."""
        queues: Dict[str, List[ModuleConfig]] = {}
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
        """Discover and register modules from installed packages.

        Looks for 'modules' package (from ContextCommerce) and calls
        its register_all() function.
        """
        if self._discovered:
            return

        self._discovered = True

        # Known module packages to try
        KNOWN_PACKAGES = [
            "modules",  # When running from Commerce dir
            "contextcommerce.modules",  # When pip installed
        ]

        for package in KNOWN_PACKAGES:
            try:
                import importlib

                mod = importlib.import_module(package)
                if hasattr(mod, "register_all"):
                    mod.register_all(self)
                    logger.info(f"Discovered modules from: {package}")
                    return  # Found one, stop looking
            except ImportError:
                continue

        logger.warning("No module packages found. Worker will have no modules.")


# Global registry instance
_registry: Optional[WorkerRegistry] = None


def get_registry() -> WorkerRegistry:
    """Get or create the global worker registry."""
    global _registry
    if _registry is None:
        _registry = WorkerRegistry()
    return _registry
