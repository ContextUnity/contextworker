"""
ContextWorker - Temporal Worker for ContextUnity.

Job orchestration for:
- Harvest: Vendor data import
- Gardener: Product enrichment (via Router)
- External modules (Commerce sync, etc.)

Usage:
    # Run all modules
    python -m contextworker
    
    # Run specific modules
    python -m contextworker --modules harvester gardener
    
    # With custom Temporal host
    python -m contextworker --temporal-host temporal.example.com:7233
"""

__version__ = "0.1.0"

from .core import WorkerRegistry, get_registry

__all__ = [
    "__version__",
    "WorkerRegistry",
    "get_registry",
]
