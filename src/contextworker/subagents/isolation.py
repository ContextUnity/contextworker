"""Isolation Management for Sub-Agents."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict

logger = logging.getLogger(__name__)


@dataclass
class IsolationContext:
    """Isolation context for sub-agents."""

    tenant_id: str | None
    session_id: str | None
    trace_id: str
    parent_agent_id: str
    subagent_id: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> IsolationContext:
        """Create from dictionary."""
        return cls(
            tenant_id=data.get("tenant_id"),
            session_id=data.get("session_id"),
            trace_id=data.get("trace_id", ""),
            parent_agent_id=data.get("parent_agent_id", ""),
            subagent_id=data.get("subagent_id", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tenant_id": self.tenant_id,
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "parent_agent_id": self.parent_agent_id,
            "subagent_id": self.subagent_id,
        }


@dataclass
class IsolatedEnvironment:
    """Isolated environment for sub-agent execution."""

    redis_key_prefix: str
    db_schema: str
    checkpoint_thread_id: str
    isolation_context: IsolationContext

    def __init__(
        self,
        redis_key_prefix: str,
        db_schema: str,
        checkpoint_thread_id: str,
        isolation_context: IsolationContext,
    ):
        self.redis_key_prefix = redis_key_prefix
        self.db_schema = db_schema
        self.checkpoint_thread_id = checkpoint_thread_id
        self.isolation_context = isolation_context


class IsolationManager:
    """Manages isolation for sub-agents."""

    async def create_isolated_environment(
        self,
        isolation_context: IsolationContext,
    ) -> IsolatedEnvironment:
        """Create isolated environment for sub-agent.

        Args:
            isolation_context: Isolation context

        Returns:
            Isolated environment
        """
        # Create Redis key prefix from session_id
        redis_key_prefix = (
            f"{isolation_context.session_id}:" if isolation_context.session_id else f"{isolation_context.subagent_id}:"
        )

        # Create DB schema from tenant_id
        db_schema = isolation_context.tenant_id or "public"

        # Create checkpoint thread_id from session_id or subagent_id
        checkpoint_thread_id = isolation_context.session_id or isolation_context.subagent_id

        logger.info(
            "Creating isolated environment for %s: redis_prefix=%s, db_schema=%s, checkpoint_thread=%s",
            isolation_context.subagent_id,
            redis_key_prefix,
            db_schema,
            checkpoint_thread_id,
        )

        return IsolatedEnvironment(
            redis_key_prefix=redis_key_prefix,
            db_schema=db_schema,
            checkpoint_thread_id=checkpoint_thread_id,
            isolation_context=isolation_context,
        )

    async def cleanup_isolated_environment(
        self,
        environment: IsolatedEnvironment,
    ) -> None:
        """Cleanup isolated environment.

        Args:
            environment: Isolated environment to cleanup
        """
        logger.info("Cleaning up isolated environment for %s", environment.isolation_context.subagent_id)
        # TODO: Implement cleanup logic (close connections, etc.)


__all__ = ["IsolationContext", "IsolatedEnvironment", "IsolationManager"]
