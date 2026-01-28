"""Harvester plugin registry with auto-discovery.

This module provides automatic discovery and registration of fetchers/transformers
from configured plugin directories. Commerce (or any host) can register its
plugins without modifying PYTHONPATH.

Usage:
    # In commerce, during startup:
    from contextworker.harvester.registry import harvester_registry
    harvester_registry.discover_plugins("/path/to/contextcommerce/src/harvester")

    # In worker:
    fetcher = harvester_registry.get_fetcher("supplier_code")
    transformer = harvester_registry.get_transformer("supplier_code")
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Type

logger = logging.getLogger(__name__)


class HarvesterRegistry:
    """Registry for harvester fetchers and transformers.

    Supports:
    - Explicit registration via decorators
    - Auto-discovery from directories
    - Fallback to PYTHONPATH (legacy mode)
    """

    def __init__(self):
        self._fetchers: Dict[str, Type[Any]] = {}
        self._transformers: Dict[str, Type[Any]] = {}
        self._discovered_paths: set[str] = set()

    # =========================================================================
    # Decorator Registration
    # =========================================================================

    def register_fetcher(self, supplier_code: str) -> Callable[[Type], Type]:
        """Decorator to register a fetcher class.

        Example:
            @harvester_registry.register_fetcher("nova_poshta")
            class NovaPoshtaFetcher:
                async def fetch(self, config) -> list[dict]: ...
        """

        def decorator(cls: Type) -> Type:
            self._fetchers[supplier_code.lower()] = cls
            logger.debug(f"Registered fetcher: {supplier_code} -> {cls.__name__}")
            return cls

        return decorator

    def register_transformer(self, supplier_code: str) -> Callable[[Type], Type]:
        """Decorator to register a transformer class.

        Example:
            @harvester_registry.register_transformer("nova_poshta")
            class NovaPoshtaTransformer:
                def transform(self, raw_data: dict) -> dict: ...
        """

        def decorator(cls: Type) -> Type:
            self._transformers[supplier_code.lower()] = cls
            logger.debug(f"Registered transformer: {supplier_code} -> {cls.__name__}")
            return cls

        return decorator

    # =========================================================================
    # Auto-Discovery
    # =========================================================================

    def discover_plugins(self, plugin_dir: str | Path) -> int:
        """Discover and load plugins from a directory.

        Expected structure:
            plugin_dir/
            ├── fetchers/
            │   ├── __init__.py
            │   ├── supplier_a.py   # Contains SupplierAFetcher class
            │   └── supplier_b.py
            └── transformers/
                ├── __init__.py
                ├── supplier_a.py   # Contains SupplierATransformer class
                └── supplier_b.py

        Args:
            plugin_dir: Path to plugin directory (e.g., contextcommerce/src/harvester)

        Returns:
            Number of plugins discovered.
        """
        plugin_path = Path(plugin_dir)
        path_str = str(plugin_path.resolve())

        if path_str in self._discovered_paths:
            logger.debug(f"Already discovered: {plugin_path}")
            return 0

        if not plugin_path.exists():
            logger.warning(f"Plugin directory not found: {plugin_path}")
            return 0

        discovered = 0

        # Discover fetchers
        fetchers_dir = plugin_path / "fetchers"
        if fetchers_dir.exists():
            discovered += self._discover_from_dir(
                fetchers_dir, "Fetcher", self._fetchers
            )

        # Discover transformers
        transformers_dir = plugin_path / "transformers"
        if transformers_dir.exists():
            discovered += self._discover_from_dir(
                transformers_dir, "Transformer", self._transformers
            )

        self._discovered_paths.add(path_str)
        logger.info(f"Discovered {discovered} plugins from {plugin_path}")
        return discovered

    def _discover_from_dir(
        self,
        directory: Path,
        class_suffix: str,
        registry: Dict[str, Type[Any]],
    ) -> int:
        """Discover classes from a directory.

        Looks for classes named {SupplierCode}{Suffix} (e.g., NovaPoshtaFetcher).
        """
        discovered = 0

        for py_file in directory.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            supplier_code = py_file.stem  # e.g., "nova_poshta"
            expected_class = self._code_to_classname(supplier_code, class_suffix)

            try:
                # Load module dynamically
                spec = importlib.util.spec_from_file_location(
                    f"harvester_plugin_{supplier_code}",
                    py_file,
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[spec.name] = module
                    spec.loader.exec_module(module)

                    # Look for the expected class
                    if hasattr(module, expected_class):
                        cls = getattr(module, expected_class)
                        registry[supplier_code.lower()] = cls
                        discovered += 1
                        logger.debug(f"Discovered {expected_class} in {py_file}")
                    else:
                        # Try to find any class with the suffix
                        for attr_name in dir(module):
                            if attr_name.endswith(
                                class_suffix
                            ) and not attr_name.startswith("_"):
                                cls = getattr(module, attr_name)
                                if isinstance(cls, type):
                                    registry[supplier_code.lower()] = cls
                                    discovered += 1
                                    logger.debug(f"Discovered {attr_name} in {py_file}")
                                    break
            except Exception as e:
                logger.warning(f"Failed to load plugin from {py_file}: {e}")

        return discovered

    @staticmethod
    def _code_to_classname(supplier_code: str, suffix: str) -> str:
        """Convert supplier_code to ClassNameSuffix.

        e.g., "nova_poshta" + "Fetcher" -> "NovaPoshtaFetcher"
        """
        parts = supplier_code.split("_")
        return "".join(part.capitalize() for part in parts) + suffix

    # =========================================================================
    # Getters
    # =========================================================================

    def get_fetcher(self, supplier_code: str) -> Optional[Any]:
        """Get fetcher instance for supplier.

        Tries:
        1. Registered fetchers
        2. Legacy PYTHONPATH import (if auto-discovery missed it)
        """
        code = supplier_code.lower()

        # Check registered
        if code in self._fetchers:
            return self._fetchers[code]()

        # Legacy fallback
        return self._legacy_import("fetchers", supplier_code, "Fetcher")

    def get_transformer(self, supplier_code: str) -> Optional[Any]:
        """Get transformer instance for supplier."""
        code = supplier_code.lower()

        if code in self._transformers:
            return self._transformers[code]()

        return self._legacy_import("transformers", supplier_code, "Transformer")

    def _legacy_import(
        self,
        module_type: str,
        supplier_code: str,
        class_suffix: str,
    ) -> Optional[Any]:
        """Legacy import via PYTHONPATH (for backwards compatibility)."""
        try:
            module_name = f"{module_type}.{supplier_code}"
            class_name = self._code_to_classname(supplier_code, class_suffix)
            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)
            return cls()
        except (ImportError, AttributeError) as e:
            logger.debug(f"Legacy import failed for {supplier_code}: {e}")
            return None

    def list_fetchers(self) -> list[str]:
        """List all registered fetcher supplier codes."""
        return list(self._fetchers.keys())

    def list_transformers(self) -> list[str]:
        """List all registered transformer supplier codes."""
        return list(self._transformers.keys())


# Global singleton
harvester_registry = HarvesterRegistry()


__all__ = ["HarvesterRegistry", "harvester_registry"]
