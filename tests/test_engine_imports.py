"""Import-time regression guards for worker task engines.

The engine modules annotate runtime signatures with ``RedisHuey`` / ``SqliteHuey``
and ``Temporal`` types that are imported only under ``TYPE_CHECKING``. Without
``from __future__ import annotations`` those annotations are evaluated at import
time and raise ``NameError: name 'RedisHuey' is not defined`` — crashing the
worker on startup. Importing each module (and instantiating the engine) proves
the annotations stay lazy.
"""

from __future__ import annotations

import importlib

import pytest

_ENGINE_MODULES = [
    "contextunity.worker.engines.base",
    "contextunity.worker.engines.huey_engine",
    "contextunity.worker.engines.temporal_engine",
]


@pytest.mark.parametrize("module_name", _ENGINE_MODULES)
def test_engine_module_imports_without_nameerror(module_name):
    """Each engine module must import cleanly (no runtime annotation evaluation)."""
    module = importlib.import_module(module_name)
    assert module is not None


def test_huey_engine_instantiates_without_redis():
    """``HueyEngine()`` must construct even though its ``__init__`` annotation
    references the ``TYPE_CHECKING``-only ``RedisHuey``/``SqliteHuey`` names."""
    from contextunity.worker.engines.huey_engine import HueyEngine

    engine = HueyEngine()
    assert engine.huey is None


pytestmark = pytest.mark.unit
