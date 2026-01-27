"""
Agent Registry for ContextWorker.

All background agents must be registered here to be discoverable.
"""

from typing import Dict, Type, List
import logging

logger = logging.getLogger(__name__)

# Registry storage
_agents: Dict[str, Type["BaseAgent"]] = {}


def register(name: str):
    """Decorator to register an agent class."""

    def decorator(cls):
        _agents[name] = cls
        logger.debug(f"Registered agent: {name}")
        return cls

    return decorator


def get_agent(name: str) -> Type["BaseAgent"]:
    """Get agent class by name."""
    if name not in _agents:
        raise ValueError(f"Unknown agent: {name}. Available: {list(_agents.keys())}")
    return _agents[name]


def list_agents() -> List[str]:
    """List all registered agent names."""
    return list(_agents.keys())


class BaseAgent:
    """
    Base class for all background agents.

    Subclasses must implement:
    - name: str - unique identifier
    - run() - main execution loop (sync or async)
    """

    name: str = "base"

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._running = False

    def start(self):
        """Start the agent loop (handles both sync and async run methods)."""
        import asyncio
        import inspect

        logger.info(f"Starting agent: {self.name}")
        self._running = True

        try:
            if inspect.iscoroutinefunction(self.run):
                # Async agent
                asyncio.run(self.run())
            else:
                # Sync agent
                self.run()
        except KeyboardInterrupt:
            logger.info(f"Agent {self.name} stopped by user")
        finally:
            self._running = False

    def stop(self):
        """Signal the agent to stop."""
        self._running = False

    def run(self):
        """Main loop - override in subclass (sync or async)."""
        raise NotImplementedError


# Import agents to trigger registration
# These imports are at the bottom to avoid circular imports
def _load_agents():
    try:
        from .agents import gardener  # noqa: F401
        from .agents import harvester  # noqa: F401
        from .agents import lexicon  # noqa: F401
    except ImportError as e:
        logger.warning(f"Some agents failed to load: {e}")


_load_agents()
